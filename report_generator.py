"""
report_generator.py
-------------------
BlockTrace Forensic Investigation Report Generator.

Compiles graph query results from Neo4j into a professional, tamper-evident
PDF dossier using ReportLab.
- Dark brown, burnt orange accent, and warm cream styling.
- Pure vector graphics logo mark (no network access, no external fonts).
- NumberedCanvas with "Page X of Y" and running headers/footers.
- Repeatable table headers, zebra striping, and clean typography.
"""

import os
import re
from datetime import datetime, timezone
from dotenv import load_dotenv
from neo4j import GraphDatabase

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
)

import graph_queries
from logic import (
    short, risk_tier, compute_wallet_risk, build_narrative, check_sanctions, unique_rows,
    describe_scope, describe_cap, describe_sanctions_snapshot, describe_data_quality
)
from report_theme import (
    COLOR_PRIMARY_DARK, COLOR_PRIMARY_ACCENT, COLOR_BG_CREAM,
    COLOR_BORDER, COLOR_SANCTIONED, COLOR_HIGH_RISK,
    COLOR_MED_RISK, COLOR_LOW_RISK, COLOR_BLUE_ACCENT,
    COLOR_VIOLET_ACCENT, COLOR_ZEBRA_ROW, COLOR_WHITE,
    COLOR_TEXT_MUTED, PRINTABLE_WIDTH,
    BlockTraceNumberedCanvas, build_report_styles,
    build_header_band, build_kpi_card_row, build_accent_callout,
    build_section_header, build_styled_table, SectionBlock
)

load_dotenv(override=True)

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


# The queries live in graph_queries.py, shared with the API, so the dossier counts
# wallets and transactions exactly like the graph, summary and Findings (scoped to the
# request's workspace and its "Show 0-ETH contract calls" choice). unique_rows stays
# as a safety net against repeated rows.

def get_summary_stats(session):
    return graph_queries.summary_stats(session)


def get_data_window(session):
    return graph_queries.data_window(session)["data_window"]


def get_hub_wallets(session, top_n=10):
    return unique_rows(graph_queries.hub_wallets(session, limit=top_n))


def get_fanout_wallets(session, min_recipients=4):
    return unique_rows(graph_queries.fanout_wallets(session, min_recipients=min_recipients, limit=10))


def get_peel_chains(session):
    return unique_rows(graph_queries.peel_chains(session, limit=10))


def get_round_number_transactions(session, min_value=1.0, limit=10):
    return graph_queries.round_number_transactions(session, min_value=min_value, limit=limit)


def get_circular_flows(session, max_hops=4, limit=10):
    return unique_rows(graph_queries.circular_flows(session, max_hops=max_hops, limit=limit))


def get_all_wallet_addresses(session):
    return graph_queries.all_wallet_addresses(session)


def narrative_to_reportlab_markup(html_text):
    """Converts browser-style HTML tags from logic.build_narrative into ReportLab markup."""
    text = html_text.replace("<strong>", "<b>").replace("</strong>", "</b>")
    text = re.sub(r"<span class='tc-mono'>", "<font face='Courier'>", text)
    text = text.replace("</span>", "</font>")
    return text


def generate_report(start_wallet, output_path="investigation_report.pdf", certificate_info=None, data_window=None,
                    scope=None, limited_wallets=None, data_quality=None):
    """Generates the official BlockTrace forensic PDF dossier.

    Args:
        start_wallet: Initial subject/target wallet address.
        output_path: Path where the generated PDF will be saved.
        certificate_info: Optional dict with 'certificate_hash', 'previous_hash', 'created_at'.
        data_window: Optional "Data window: ..." line; computed from the graph if omitted.
        scope: Optional trace scope (dates, order, tx cap, hops, chain) shown as "Investigation scope".
        limited_wallets: Wallets whose transactions were cut off by the per-wallet cap.
        data_quality: Optional counts from the API (fetched, shown, failed, 0-ETH, capped).
    """
    styles = build_report_styles()
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        title="BlockTrace Forensic Investigation Report",
        author="BlockTrace",
        subject="Blockchain forensic investigation findings"
    )

    elements = []

    # Timestamp
    gen_time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Investigation ID (if certified)
    inv_id = None
    if certificate_info and certificate_info.get("certificate_hash"):
        inv_id = certificate_info["certificate_hash"]





    with driver.session(database=NEO4J_DATABASE) as session:
        wallets, txs = get_summary_stats(session)
        dw = data_window or get_data_window(session)
        header_rows = [("Investigation scope", describe_scope(scope) or "Not recorded for this graph")]
        if limited_wallets:
            header_rows.append(("Transaction cap", describe_cap(limited_wallets)))
        if data_quality:
            header_rows.append(("Data quality", describe_data_quality(data_quality)))
        header_rows.append(("Sanctions list", describe_sanctions_snapshot()))
        elements.append(build_header_band(start_wallet, gen_time_str, styles, investigation_id=inv_id,
                                          data_window=dw, extra_rows=header_rows))
        elements.append(Spacer(1, 10))
        hub_data = get_hub_wallets(session)
        fanout_data = get_fanout_wallets(session)
        peel_data = get_peel_chains(session)
        round_data = get_round_number_transactions(session)
        circular_data = get_circular_flows(session)
        all_addresses = get_all_wallet_addresses(session)
        sanctions_matches = check_sanctions(all_addresses)
        sanctioned_set = {addr for addr, _ in sanctions_matches}
        risk_rows = compute_wallet_risk(
            hub_data, fanout_data, peel_data, round_data, circular_data,
            sanctioned_addresses=sanctioned_set
        )

        # 2. KPI Cards Row
        overall_tier_label = "LOW RISK"
        overall_tier_color = COLOR_LOW_RISK
        if risk_rows:
            top_score = risk_rows[0][2]
            if any(s == "OFAC Sanctioned" for _, signals, _ in risk_rows for s in signals):
                overall_tier_label, overall_tier_color = "SANCTIONED MATCH", COLOR_SANCTIONED
            elif top_score >= 3:
                overall_tier_label, overall_tier_color = "HIGH RISK", COLOR_HIGH_RISK
            elif top_score == 2:
                overall_tier_label, overall_tier_color = "MEDIUM RISK", COLOR_MED_RISK

        badges = [
            ("Overall Status", overall_tier_label, overall_tier_color),
            ("Wallets Traced", wallets, COLOR_PRIMARY_DARK),
            ("Transactions", txs, COLOR_PRIMARY_DARK),
            ("Flagged Wallets", len(risk_rows), COLOR_PRIMARY_DARK),
        ]
        elements.append(build_kpi_card_row(badges, styles))
        elements.append(Spacer(1, 12))

        # 3. What This Trail Shows (Narrative Box)
        narrative_paragraphs = build_narrative(
            start_wallet, wallets, txs, hub_data, fanout_data, peel_data, round_data, circular_data, risk_rows
        )

        narrative_items = []
        for p in narrative_paragraphs:
            cleaned = narrative_to_reportlab_markup(p)
            bullet_html = f"<font color='{COLOR_PRIMARY_ACCENT.hexval()}'>&#9642;</font>&nbsp; {cleaned}"
            narrative_items.append(Paragraph(bullet_html, styles['BulletItem']))

        narrative_items.append(Spacer(1, 4))
        narrative_items.append(Paragraph(
            "These patterns are heuristic indicators derived from public blockchain data, not proof "
            "of wrongdoing. Review by a qualified investigator is recommended before drawing conclusions.",
            styles['Disclaimer']
        ))

        elements.append(build_accent_callout(
            "What This Trail Shows", narrative_items,
            accent_color=COLOR_PRIMARY_ACCENT, bg_color=COLOR_BG_CREAM, styles=styles
        ))
        elements.append(Spacer(1, 10))
    

        def add_section(title, subtitle, content_flowable, accent_color):
            hdr = build_section_header(title, subtitle, accent_color=accent_color, styles=styles)
            if isinstance(content_flowable, Paragraph):
                elements.append(KeepTogether([hdr, content_flowable]))
            else:
                block = SectionBlock(hdr, content_flowable, min_rows=3)
                elements.append(block)
        

        # 4. Sanctions Screening
        if sanctions_matches:
            sanctions_rows = []
            for addr, entry in sanctions_matches:
                match_desc = f"<b>{entry.get('name', 'Unknown Entity')}</b> &mdash; {entry.get('authority', 'OFAC SDN')}"
                sanctions_rows.append([
                    Paragraph(f"<font face='Courier'>{addr}</font>", styles['TableCellMono']),
                    Paragraph(match_desc, styles['TableCell'])
                ])

            sanctions_content = build_styled_table(
                ["Wallet Address", "Sanctions Match Details"],
                sanctions_rows,
                [8.2 * cm, 9.2 * cm],
                COLOR_SANCTIONED,
                styles=styles
            )
        else:
            sanctions_content = Paragraph(
                "No wallets in this trace matched the OFAC sanctions list snapshot.",
                styles['Body']
            )

        add_section(
            "Sanctions Screening",
            f"Cross-referencing against the OFAC SDN list ({describe_sanctions_snapshot()}). "
            "A dated snapshot; verify matches against official OFAC sources.",
            sanctions_content,
            COLOR_SANCTIONED
        )

        # 5. Wallet Risk Overview
        if risk_rows:
            risk_table_rows = []
            for wallet, signals, score in risk_rows:
                tier_label, _ = risk_tier(score)
                pill_bg = COLOR_LOW_RISK if tier_label == "Low" else (COLOR_MED_RISK if tier_label == "Medium" else COLOR_HIGH_RISK)
                if "OFAC Sanctioned" in signals:
                    pill_bg = COLOR_SANCTIONED
                    tier_label = "SANCTIONED"

                signal_plural = "signal" if score == 1 else "signals"
                tier_html = f"<font color='{pill_bg.hexval()}'><b>&#9679; {tier_label.upper()}</b></font> ({score} {signal_plural})"

                signals_str = " &bull; ".join(signals)

                wallet_cell = Paragraph(
                    f"<font face='Courier' size='8'><b>{wallet}</b></font><br/>"
                    f"<font color='{COLOR_TEXT_MUTED.hexval()}' size='6.5'>{signals_str}</font>",
                    styles['TableCell']
                )
                risk_table_rows.append([wallet_cell, Paragraph(tier_html, styles['TableCellRight'])])

            risk_content = build_styled_table(
                ["Wallet & Detected Behaviors", "Risk Assessment"],
                risk_table_rows,
                [12.4 * cm, 5.0 * cm],
                COLOR_PRIMARY_DARK,
                right_cols=[1],
                styles=styles
            )
        else:
            risk_content = Paragraph(
                "No wallets triggered any detection signal in this dataset.",
                styles['Body']
            )

        add_section(
            "Wallet Risk Overview",
            "Composite risk classification based on aggregated behavioral heuristic signals.",
            risk_content,
            COLOR_PRIMARY_DARK
        )

        # 6. Hub Wallets (High Activity)
        if hub_data:
            hub_rows = [
                [Paragraph(f"<font face='Courier'>{w}</font>", styles['TableCellMono']), str(c)]
                for w, c in hub_data
            ]
            hub_content = build_styled_table(
                ["Wallet Address", "Total Transactions"],
                hub_rows,
                [12.4 * cm, 5.0 * cm],
                COLOR_PRIMARY_DARK,
                right_cols=[1],
                styles=styles
            )
        else:
            hub_content = Paragraph("No hub wallets detected.", styles['Body'])

        add_section(
            "Hub Wallets (High Activity)",
            "Addresses exhibiting high transaction frequency and counterparty concentration.",
            hub_content,
            COLOR_PRIMARY_DARK
        )

        # 7. High Fan-Out Wallets
        if fanout_data:
            fanout_rows = [
                [Paragraph(f"<font face='Courier'>{w}</font>", styles['TableCellMono']), str(c)]
                for w, c in fanout_data
            ]
            fanout_content = build_styled_table(
                ["Wallet Address", "Distinct Recipients"],
                fanout_rows,
                [12.4 * cm, 5.0 * cm],
                COLOR_SANCTIONED,
                right_cols=[1],
                styles=styles
            )
        else:
            fanout_content = Paragraph("No high fan-out wallets detected.", styles['Body'])

        add_section(
            "High Fan-Out Wallets (Possible Fund Splitting)",
            "Addresses distributing funds rapidly to multiple distinct recipient wallets.",
            fanout_content,
            COLOR_SANCTIONED
        )

        # 8. Possible Peel Chains
        if peel_data:
            peel_rows = [
                [
                    Paragraph(f"<font face='Courier'>{w}</font>", styles['TableCellMono']),
                    f"{m:.4f} ETH",
                    f"{p:.4f} ETH"
                ]
                for w, m, p in peel_data
            ]
            peel_content = build_styled_table(
                ["Wallet Address", "Main Amount", "Peel Amount"],
                peel_rows,
                [9.4 * cm, 4.0 * cm, 4.0 * cm],
                COLOR_BLUE_ACCENT,
                right_cols=[1, 2],
                styles=styles
            )
        else:
            peel_content = Paragraph("No peel chain patterns detected.", styles['Body'])

        add_section(
            "Possible Peel Chains (Laundering Pattern)",
            "Asymmetric transfers where small amounts are peeled off while bulk funds continue.",
            peel_content,
            COLOR_BLUE_ACCENT
        )

        # 9. Round-Number Transactions
        if round_data:
            round_rows = [
                [
                    Paragraph(f"<font face='Courier'>{short(f)} &rarr; {short(t)}</font>", styles['TableCellMono']),
                    f"{v:.0f} ETH"
                ]
                for f, t, v in round_data
            ]
            round_content = build_styled_table(
                ["Transaction (From &rarr; To)", "Amount"],
                round_rows,
                [12.4 * cm, 5.0 * cm],
                COLOR_PRIMARY_ACCENT,
                right_cols=[1],
                styles=styles
            )
        else:
            round_content = Paragraph("No round-number transactions detected.", styles['Body'])

        add_section(
            "Round-Number Transactions",
            "Transfers of whole-integer token amounts, indicative of manual or OTC transactions.",
            round_content,
            COLOR_PRIMARY_ACCENT
        )

        # 10. Circular Flows
        if circular_data:
            circular_rows = [
                [
                    Paragraph(f"<font face='Courier'>{w}</font>", styles['TableCellMono']),
                    f"{h} hops"
                ]
                for w, h in circular_data
            ]
            circular_content = build_styled_table(
                ["Wallet Address", "Loop Length"],
                circular_rows,
                [12.4 * cm, 5.0 * cm],
                COLOR_VIOLET_ACCENT,
                right_cols=[1],
                styles=styles
            )
        else:
            circular_content = Paragraph("No circular flows detected.", styles['Body'])

        add_section(
            "Circular Flows (Possible Wash Trading)",
            "Closed loops where funds cycle back to the originating address through intermediate hops.",
            circular_content,
            COLOR_VIOLET_ACCENT
        )

        # 11. Certificate of Integrity (if issued)
        if certificate_info:
            cert_flowables = [
                Paragraph(
                    f"Certificate Hash: <font face='Courier'>{certificate_info['certificate_hash']}</font>",
                    styles['MetaValueCourier']
                ),
                Paragraph(
                    f"Previous Hash: <font face='Courier'>{certificate_info['previous_hash']}</font>",
                    styles['MetaValueCourier']
                ),
                Paragraph(f"Issued: {certificate_info.get('created_at', 'N/A')}", styles['Disclaimer']),
                Spacer(1, 4),
                Paragraph(
                    "This report's findings are sealed under the certificate hash above. Anyone can "
                    "independently verify this report has not been altered by recomputing the SHA-256 "
                    "hash of the recorded findings concatenated with the previous hash, and confirming "
                    "it matches the certificate hash &mdash; without needing to trust this document's source.",
                    styles['Disclaimer']
                ),
            ]
            elements.append(build_accent_callout(
                "Certificate of Integrity", cert_flowables,
                accent_color=COLOR_PRIMARY_DARK, bg_color=COLOR_BG_CREAM, styles=styles
            ))
        

        # 12. Verification Instructions Callout Box
        verify_flowables = [
            Paragraph(
                "After publishing, navigate to the <b>Verify Report</b> page in BlockTrace, upload this exact "
                "PDF dossier, and enter the corresponding investigation hash. The platform confirms "
                "byte-for-byte cryptographic authenticity against the immutable record anchored on the "
                "Ethereum Sepolia testnet.",
                styles['Body']
            ),
        ]
        elements.append(build_accent_callout(
            "How to Verify This Report", verify_flowables,
            accent_color=COLOR_PRIMARY_ACCENT, bg_color=COLOR_BG_CREAM, styles=styles
        ))
        elements.append(Spacer(1, 10))
        elements.append(Spacer(1, 12))

        # 13. Final Disclaimer Paragraph
        elements.append(Paragraph(
            "This report was generated using automated graph-based heuristics (hub detection, "
            "fan-out detection, peel-chain detection, round-number detection, circular-flow detection) "
            "and sanctions-list screening applied to public blockchain transaction data. Findings should "
            "be reviewed by a qualified investigator before use in any formal proceeding.",
            styles['Disclaimer']
        ))

    doc.build(elements, canvasmaker=BlockTraceNumberedCanvas)
    print(f"Report saved to {output_path}")


if __name__ == "__main__":
    generate_report("0x098B716B8Aaf21512996dC57EB0615e2383E2f96")
