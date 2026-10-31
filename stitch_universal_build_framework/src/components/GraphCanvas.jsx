import React, { useEffect, useRef, useState, useMemo } from 'react';
import * as d3 from 'd3';
import { useInvestigation } from '../context/InvestigationContext';
import { useCompact, midTruncate, copyText } from '../utils/useCompact';
import { Sheet } from './mobile/Sheet';

const EXPLORERS = {
  Ethereum: 'https://etherscan.io',
  'BNB Smart Chain': 'https://bscscan.com',
  Polygon: 'https://polygonscan.com',
};

// 2 decimals from 1 ETH, 4 below; dust under 0.0001 reads "<0.0001", never "0.0000".
const formatEth = (v) => {
  if (v >= 1) return `${v.toFixed(2)} ETH`;
  if (v >= 0.0001) return `${v.toFixed(4)} ETH`;
  if (v > 0) return '<0.0001 ETH';
  return '0 ETH';
};
const formatDate = (ts) => (ts ? new Date(ts * 1000).toISOString().slice(0, 16).replace('T', ' ') : '—');
const shortHash = (h) => (h ? `${h.slice(0, 10)}…${h.slice(-4)}` : '');

export const GraphCanvas = ({ filterQuery = '', onSelectWallet }) => {
  const {
    edges,
    activePathEdges,
    sanctions,
    entityLabels,
    isLoadingGraph,
    limitedWallets,
    traceScope,
    riskData,
    openAddressSheet,
  } = useInvestigation();
  const explorer = EXPLORERS[traceScope?.chain] || EXPLORERS.Ethereum;

  // Phones and tablets: tap instead of hover, details in a bottom sheet
  const compact = useCompact();
  const compactRef = useRef(compact);
  compactRef.current = compact;

  const svgRef = useRef(null);
  const containerRef = useRef(null);
  // The zoom behaviour bound to the SVG, so the +/-/Fit buttons drive the same one
  const zoomRef = useRef(null);
  const nodesRef = useRef([]);
  // Latest callback without rebuilding the graph (a new function each render used to
  // rebuild the SVG and reset the zoom on every wallet click)
  const onSelectRef = useRef(onSelectWallet);
  onSelectRef.current = onSelectWallet;
  const [hoveredNode, setHoveredNode] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [selectedEdge, setSelectedEdge] = useState(null);
  const [legendOpen, setLegendOpen] = useState(false);

  // Set of sanctioned addresses
  const sanctionedSet = useMemo(() => {
    return new Set(sanctions.map((s) => s.wallet.toLowerCase()));
  }, [sanctions]);

  // Wallets whose history was cut off by the per-wallet transaction cap
  const cappedSet = useMemo(() => {
    return new Set((limitedWallets || []).map((w) => w.toLowerCase()));
  }, [limitedWallets]);
  const capText = `More transactions than the cap (${traceScope?.tx_per_wallet ?? 15}); only part of this wallet's history is shown.`;

  // Edges to render: if activePathEdges is set, use it; otherwise use all edges
  const rawEdges = activePathEdges || edges;

  // Filter edges based on filterQuery
  const filteredEdges = useMemo(() => {
    if (!filterQuery) return rawEdges;
    const q = filterQuery.toLowerCase().trim();
    return rawEdges.filter(
      (e) =>
        e.from.toLowerCase().includes(q) ||
        e.to.toLowerCase().includes(q) ||
        (entityLabels[e.from.toLowerCase()] && entityLabels[e.from.toLowerCase()].toLowerCase().includes(q)) ||
        (entityLabels[e.to.toLowerCase()] && entityLabels[e.to.toLowerCase()].toLowerCase().includes(q))
    );
  }, [rawEdges, filterQuery, entityLabels]);

  // Nodes and links from the filtered edges. Each wallet keeps what it sent and
  // received separately (never summed), its transactions and first/last seen. Several
  // transactions between the same pair become one link labelled "N txs · total", whose
  // tooltip lists them, so the line and the wallet panel always agree.
  const { nodes, links } = useMemo(() => {
    const nodeMap = new Map();
    const linkMap = new Map();

    const nodeFor = (address) => {
      const key = address.toLowerCase();
      if (!nodeMap.has(key)) {
        nodeMap.set(key, {
          id: key,
          address,
          isSanctioned: sanctionedSet.has(key),
          isCapped: cappedSet.has(key),
          label: entityLabels[key] || null,
          inDegree: 0,
          outDegree: 0,
          sentTotal: 0,
          receivedTotal: 0,
          firstSeen: null,
          lastSeen: null,
          txs: [],
        });
      }
      return nodeMap.get(key);
    };

    filteredEdges.forEach((e) => {
      const value = Number(e.value || 0);
      const from = nodeFor(e.from);
      const to = nodeFor(e.to);
      const tx = { hash: e.hash || null, timestamp: e.timestamp || null, value, kind: e.kind || 'normal', failed: !!e.failed };

      from.outDegree += 1;
      from.sentTotal += value;
      from.txs.push({ ...tx, direction: 'out', counterparty: e.to });
      to.inDegree += 1;
      to.receivedTotal += value;
      to.txs.push({ ...tx, direction: 'in', counterparty: e.from });
      [from, to].forEach((n) => {
        if (tx.timestamp) {
          n.firstSeen = n.firstSeen === null ? tx.timestamp : Math.min(n.firstSeen, tx.timestamp);
          n.lastSeen = n.lastSeen === null ? tx.timestamp : Math.max(n.lastSeen, tx.timestamp);
        }
      });

      const pairKey = `${from.id}->${to.id}`;
      if (!linkMap.has(pairKey)) {
        linkMap.set(pairKey, { id: pairKey, source: from.id, target: to.id, value: 0, count: 0, txs: [] });
      }
      const link = linkMap.get(pairKey);
      link.value += value;
      link.count += 1;
      link.txs.push(tx);
    });

    nodeMap.forEach((n) => n.txs.sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0)));

    return {
      nodes: Array.from(nodeMap.values()),
      links: Array.from(linkMap.values()),
    };
  }, [filteredEdges, sanctionedSet, cappedSet, entityLabels]);

  // Shorten address helper
  const truncate = (addr) => {
    if (!addr) return '';
    return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
  };

  // D3 Force Simulation Setup
  useEffect(() => {
    if (!svgRef.current || !containerRef.current) return;

    const width = containerRef.current.clientWidth || 800;
    const height = containerRef.current.clientHeight || 600;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove(); // Clear previous render

    if (nodes.length === 0) {
      return;
    }

    // Define Arrow Marker
    const defs = svg.append('defs');
    defs
      .append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 24) // offset from node center
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#FF6D1F');

    defs
      .append('marker')
      .attr('id', 'arrowhead-sanctioned')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 24)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#D62839');

    // Create Main Container for Zoom
    const g = svg.append('g').attr('class', 'main-group');

    // On small screens line labels are hidden when zoomed out (clutter, and the
    // per-tick label layout is the most expensive step)
    let labelsHidden = compactRef.current;
    let placeLabels = () => {};

    // Zoom behavior
    const zoom = d3
      .zoom()
      .scaleExtent([0.15, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
        const hide = compactRef.current && event.transform.k < 1.1;
        if (hide !== labelsHidden) {
          labelsHidden = hide;
          linkLabelLayer.attr('display', hide ? 'none' : null);
          if (!hide) placeLabels();
        }
      });
    zoomRef.current = zoom;

    svg.call(zoom);

    // Initial centering
    svg.call(zoom.transform, d3.zoomIdentity.translate(width / 2, height / 2).scale(0.85));

    // Force Simulation
    const simulation = d3
      .forceSimulation(nodes)
      .force(
        'link',
        d3
          .forceLink(links)
          .id((d) => d.id)
          .distance(120)
      )
      .force('charge', d3.forceManyBody().strength(-380))
      .force('center', d3.forceCenter(0, 0))
      .force('collision', d3.forceCollide().radius(40));
    // Small screens: settle in about half the ticks (less work on phone CPUs)
    if (compactRef.current) simulation.alphaDecay(0.05);

    // Render Links
    const link = g
      .append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(links)
      .enter()
      .append('line')
      .attr('stroke', (d) => {
        const tgt = typeof d.target === 'object' ? d.target : { address: d.target };
        return sanctionedSet.has(tgt.address?.toLowerCase()) ? '#D62839' : 'rgba(255, 109, 31, 0.45)';
      })
      .attr('stroke-width', (d) => Math.max(1.5, Math.min(6, Math.log10(d.value + 1) * 2)))
      .attr('stroke-opacity', 0.8)
      .attr('marker-end', (d) => {
        const tgt = typeof d.target === 'object' ? d.target : { address: d.target };
        return sanctionedSet.has(tgt.address?.toLowerCase()) ? 'url(#arrowhead-sanctioned)' : 'url(#arrowhead)';
      });

    // Wide invisible lines on small screens so a finger can hit a line
    const linkHit = compactRef.current
      ? g
          .append('g')
          .attr('class', 'link-hits')
          .selectAll('line')
          .data(links)
          .enter()
          .append('line')
          .attr('stroke', 'transparent')
          .attr('stroke-width', 18)
          .style('cursor', 'pointer')
          .on('click', (event, d) => {
            event.stopPropagation();
            setSelectedNode(null);
            setSelectedEdge(d);
          })
      : null;

    // Hover list of the transactions behind each line
    link.append('title').text((d) =>
      d.txs
        .map((t) => `${formatDate(t.timestamp)}  ${formatEth(t.value)}${t.kind === 'internal' ? ' (internal)' : ''}${t.hash ? `  ${shortHash(t.hash)}` : ''}`)
        .join('\n')
    );

    // Link value labels: a small pill beside each line's midpoint. Drawn above the nodes
    // (raised after they are added) and hidden on lines too short to fit them, so a
    // label never sits on a wallet or its address.
    const linkLabelLayer = g
      .append('g')
      .attr('class', 'link-labels')
      .style('pointer-events', 'none')
      .attr('display', labelsHidden ? 'none' : null);
    const linkText = linkLabelLayer
      .selectAll('g')
      .data(links)
      .enter()
      .append('g');
    linkText
      .append('rect')
      .attr('rx', 6)
      .attr('ry', 6)
      .attr('fill', '#1b1c1c')
      .attr('fill-opacity', 0.85)
      .attr('stroke', 'rgba(255, 109, 31, 0.35)')
      .attr('stroke-width', 0.75);
    linkText
      .append('text')
      .attr('font-family', 'JetBrains Mono')
      .attr('font-size', '9px')
      .attr('fill', '#eed5cb')
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'central')
      .text((d) => (d.count > 1 ? `${d.count} txs · ${formatEth(d.value)}` : formatEth(d.value)));
    // Size each pill to its text (approximate if the browser cannot measure yet)
    linkText.each(function (d) {
      const text = d3.select(this).select('text');
      let width = text.node().getComputedTextLength?.() || 0;
      if (!width) width = text.text().length * 5.4;
      d.labelWidth = width + 10;
      d3.select(this)
        .select('rect')
        .attr('x', -d.labelWidth / 2)
        .attr('y', -7)
        .attr('width', d.labelWidth)
        .attr('height', 14);
    });

    // Render Node Groups
    const node = g
      .append('g')
      .attr('class', 'nodes')
      .selectAll('g')
      .data(nodes)
      .enter()
      .append('g')
      .attr('class', 'node')
      .style('cursor', 'pointer')
      .call(
        d3
          .drag()
          .on('start', (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on('drag', (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on('end', (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          })
      );

    const nodeRadius = (d) => Math.max(14, Math.min(28, 14 + (d.inDegree + d.outDegree) * 1.5));

    // Dashed amber ring around wallets that hit the transaction cap
    node
      .filter((d) => d.isCapped)
      .append('circle')
      .attr('class', 'cap-ring')
      .attr('r', (d) => nodeRadius(d) + 5)
      .attr('fill', 'none')
      .attr('stroke', '#F2A93B')
      .attr('stroke-width', 2)
      .attr('stroke-dasharray', '4 3');

    node.append('title').text((d) => (d.isCapped ? `${d.address}
${capText}` : d.address));

    // Node Circles
    node
      .append('circle')
      .attr('class', 'node-core')
      .attr('r', (d) => {
        const degree = d.inDegree + d.outDegree;
        return Math.max(14, Math.min(28, 14 + degree * 1.5));
      })
      .attr('fill', (d) => {
        if (d.isSanctioned) return '#D62839';
        if (d.label) return '#FF6D1F';
        return '#1b1c1c';
      })
      .attr('stroke', (d) => {
        if (d.isSanctioned) return '#ffdad6';
        if (d.label) return '#ffdbcd';
        return '#e1bfb2';
      })
      .attr('stroke-width', 2.5)
      .attr('filter', (d) => (d.isSanctioned ? 'drop-shadow(0 0 8px rgba(214, 40, 57, 0.7))' : 'none'));

    // Inner icon / symbol
    node
      .append('text')
      .attr('class', 'material-symbols-outlined')
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'central')
      .attr('font-size', '14px')
      .attr('fill', '#ffffff')
      .text((d) => {
        if (d.isSanctioned) return 'warning';
        if (d.label) return 'star';
        return 'account_balance_wallet';
      });

    // Node Address Label below circle
    node
      .append('text')
      .attr('dy', (d) => {
        const degree = d.inDegree + d.outDegree;
        const radius = Math.max(14, Math.min(28, 14 + degree * 1.5));
        return radius + 14;
      })
      .attr('text-anchor', 'middle')
      .attr('font-family', 'JetBrains Mono')
      .attr('font-size', '10px')
      .attr('font-weight', '500')
      .attr('fill', '#ffede7')
      .attr('paint-order', 'stroke')
      .attr('stroke', '#3c2d27')
      .attr('stroke-width', 3)
      .text((d) => (d.label ? `${d.label} (${truncate(d.address)})` : truncate(d.address)))
      .each(function (d) {
        // Remember each wallet's footprint (circle + address label) for edge-label collisions
        d.radius = nodeRadius(d);
        d.textWidth = this.getComputedTextLength?.() || this.textContent.length * 6;
      });

    linkLabelLayer.raise();

    // Interactions (hover only with a mouse; touch taps open the bottom sheet)
    node
      .on('mouseenter', (event, d) => {
        if (compactRef.current) return;
        setHoveredNode(d);
        d3.select(event.currentTarget).select('circle.node-core').attr('stroke', '#ffffff').attr('stroke-width', 3.5);
      })
      .on('mouseleave', (event, d) => {
        if (compactRef.current) return;
        setHoveredNode(null);
        d3.select(event.currentTarget)
          .select('circle.node-core')
          .attr('stroke', d.isSanctioned ? '#ffdad6' : d.label ? '#ffdbcd' : '#e1bfb2')
          .attr('stroke-width', 2.5);
      })
      .on('click', (event, d) => {
        event.stopPropagation();
        setSelectedNode(d);
        setSelectedEdge(null);
        if (onSelectRef.current) {
          onSelectRef.current(d.address);
        }
      });

    svg.on('click', () => {
      setSelectedNode(null);
      setSelectedEdge(null);
    });

    nodesRef.current = nodes;
    let fitted = false;

    // Simulation Tick Updates
    simulation.on('tick', () => {
      link
        .attr('x1', (d) => d.source.x)
        .attr('y1', (d) => d.source.y)
        .attr('x2', (d) => d.target.x)
        .attr('y2', (d) => d.target.y);
      if (linkHit) {
        linkHit
          .attr('x1', (d) => d.source.x)
          .attr('y1', (d) => d.source.y)
          .attr('x2', (d) => d.target.x)
          .attr('y2', (d) => d.target.y);
      }

      node.attr('transform', (d) => `translate(${d.x},${d.y})`);
      if (!labelsHidden) placeLabels();
    });

    // Small screens: frame the whole graph once the layout has settled
    simulation.on('end', () => {
      if (compactRef.current && !fitted) {
        fitted = true;
        fitToView(0);
      }
    });

    placeLabels = () => {
      // Each wallet's circle and address label as boxes, for the edge-label checks below
      const boxes = [];
      nodes.forEach((n) => {
        const r = n.radius || 14;
        const w = (n.textWidth || 60) / 2 + 3;
        boxes.push([n.x - r, n.y - r, n.x + r, n.y + r]);
        boxes.push([n.x - w, n.y + r + 3, n.x + w, n.y + r + 21]);
      });
      linkText.each(function (d) {
        const dx = d.target.x - d.source.x;
        const dy = d.target.y - d.source.y;
        const len = Math.hypot(dx, dy) || 1;
        // Shift perpendicular to the line so the pill sits beside it, not on it
        const cx = (d.source.x + d.target.x) / 2 + (-dy / len) * 9;
        const cy = (d.source.y + d.target.y) / 2 + (dx / len) * 9;
        const half = d.labelWidth / 2;
        // Hide the pill wherever it would cover a wallet or its address
        const blocked = boxes.some(([x1, y1, x2, y2]) => cx - half < x2 && cx + half > x1 && cy - 8 < y2 && cy + 8 > y1);
        d3.select(this)
          .attr('transform', `translate(${cx},${cy})`)
          .attr('display', blocked ? 'none' : null);
      });
    };

    return () => {
      simulation.stop();
    };
  }, [nodes, links, sanctionedSet, capText, compact]);

  // Zoom Controls (use the zoom behaviour bound to the SVG; a fresh d3.zoom() has no
  // listener, so the view never moved)
  const handleZoom = (scaleFactor) => {
    if (!svgRef.current || !zoomRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.transition().duration(300).call(zoomRef.current.scaleBy, scaleFactor);
  };

  // Fit every wallet into the view
  const fitToView = (duration = 400) => {
    if (!svgRef.current || !containerRef.current || !zoomRef.current) return;
    const width = containerRef.current.clientWidth || 800;
    const height = containerRef.current.clientHeight || 600;
    const pts = nodesRef.current.filter((n) => Number.isFinite(n.x) && Number.isFinite(n.y));
    const svg = d3.select(svgRef.current);
    let t = d3.zoomIdentity.translate(width / 2, height / 2).scale(0.85);
    if (pts.length) {
      const pad = 60;
      const minX = d3.min(pts, (n) => n.x) - pad;
      const maxX = d3.max(pts, (n) => n.x) + pad;
      const minY = d3.min(pts, (n) => n.y) - pad;
      const maxY = d3.max(pts, (n) => n.y) + pad;
      const k = Math.max(0.15, Math.min(1.5, Math.min(width / (maxX - minX), height / (maxY - minY))));
      t = d3.zoomIdentity.translate(width / 2 - (k * (minX + maxX)) / 2, height / 2 - (k * (minY + maxY)) / 2).scale(k);
    }
    (duration ? svg.transition().duration(duration) : svg).call(zoomRef.current.transform, t);
  };

  const handleResetZoom = () => fitToView(400);

  // Risk signals and sanctions match for the wallet sheet
  const riskFor = (address) => riskData.find((r) => r.wallet?.toLowerCase() === address?.toLowerCase()) || null;
  const sanctionFor = (address) => sanctions.find((s) => s.wallet?.toLowerCase() === address?.toLowerCase()) || null;

  return (
    <div ref={containerRef} className="w-full h-full relative bg-inverse-surface overflow-hidden select-none">
      {/* Empty State */}
      {nodes.length === 0 && !isLoadingGraph && (
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-8 z-10">
          <div className="w-16 h-16 rounded-full bg-white/5 border border-outline-variant/30 flex items-center justify-center text-outline-variant mb-4">
            <span className="material-symbols-outlined text-[32px]">hub</span>
          </div>
          <h3 className="font-headline-md text-lg text-inverse-on-surface font-semibold mb-2">
            No Graph Loaded
          </h3>
          <p className="font-body-md text-sm text-outline-variant max-w-md">
            Select a verified case from the sidebar templates or input a target wallet address to trace the transaction network.
          </p>
        </div>
      )}

      {/* Loading Indicator */}
      {isLoadingGraph && (
        <div className="absolute inset-0 bg-inverse-surface/60 backdrop-blur-xs flex flex-col items-center justify-center z-20">
          <div className="w-10 h-10 border-3 border-primary border-t-transparent rounded-full animate-spin mb-3"></div>
          <span className="font-label-caps text-xs text-primary uppercase tracking-widest font-semibold">
            Synthesizing Forensic Graph...
          </span>
        </div>
      )}

      {/* SVG Canvas */}
      <svg ref={svgRef} className="w-full h-full cursor-grab active:cursor-grabbing" />

      {/* Graph Controls Toolbar */}
      <div className="absolute bottom-6 right-6 flex items-center gap-1 bg-surface/90 backdrop-blur-md p-1.5 rounded-lg border border-outline-variant shadow-xl z-20 max-lg:bottom-3 max-lg:right-3 max-lg:flex-col max-lg:p-1">
        <button
          onClick={() => handleZoom(1.3)}
          className="p-2 text-on-surface hover:text-primary hover:bg-surface-container rounded transition-colors max-lg:flex max-lg:items-center max-lg:justify-center"
          title="Zoom In"
          aria-label="Zoom in"
        >
          <span className="material-symbols-outlined text-[18px]">add</span>
        </button>
        <button
          onClick={() => handleZoom(0.7)}
          className="p-2 text-on-surface hover:text-primary hover:bg-surface-container rounded transition-colors max-lg:flex max-lg:items-center max-lg:justify-center"
          title="Zoom Out"
          aria-label="Zoom out"
        >
          <span className="material-symbols-outlined text-[18px]">remove</span>
        </button>
        <div className="w-[1px] h-4 bg-outline-variant mx-1 max-lg:w-6 max-lg:h-[1px] max-lg:my-0.5" />
        <button
          onClick={handleResetZoom}
          className="p-2 text-on-surface hover:text-primary hover:bg-surface-container rounded transition-colors max-lg:flex max-lg:items-center max-lg:justify-center"
          title="Fit to Screen"
          aria-label="Fit graph to screen"
        >
          <span className="material-symbols-outlined text-[18px]">center_focus_strong</span>
        </button>
      </div>

      {/* Small screens: legend behind a chip */}
      {compact && nodes.length > 0 && (
        <button
          type="button"
          onClick={() => setLegendOpen((v) => !v)}
          aria-expanded={legendOpen}
          className="absolute bottom-3 left-3 z-20 flex items-center gap-1.5 px-3 rounded-full bg-surface/95 border border-outline-variant shadow-lg text-xs font-label-caps uppercase font-bold text-on-surface"
        >
          <span className="material-symbols-outlined text-[18px]">legend_toggle</span>
          Legend
        </button>
      )}

      {/* Legend Overlay */}
      <div className={`absolute bottom-6 left-6 ${compact ? (legendOpen ? 'max-lg:bottom-[60px] max-lg:left-3 max-lg:right-16 max-lg:gap-x-4 max-lg:gap-y-2 max-lg:px-3 max-lg:py-2.5' : 'hidden') : ''} bg-surface/90 backdrop-blur-md px-4 py-3 rounded-lg border border-outline-variant shadow-xl z-20 flex flex-wrap items-center gap-4 text-xs font-label-caps uppercase text-on-surface`}>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-full bg-[#1b1c1c] border border-outline-variant" />
          <span>Standard Wallet</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-full bg-error border border-error-container shadow-[0_0_6px_rgba(214,40,57,0.8)]" />
          <span className="text-error font-bold">Sanctioned Entity</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-full bg-primary border border-primary-fixed" />
          <span className="text-primary font-bold">Known Label</span>
        </div>
        {cappedSet.size > 0 && (
          <div className="flex items-center gap-1.5" title={capText}>
            <div className="w-3 h-3 rounded-full border-2 border-dashed border-[#F2A93B]" />
            <span className="text-[#B7791F] font-bold">Cap Reached</span>
          </div>
        )}
      </div>

      {/* Hover Node Tooltip */}
      {hoveredNode && !compact && (
        <div
          className="absolute top-6 right-6 bg-surface border border-outline-variant rounded-xl p-4 shadow-2xl z-30 max-w-xs animate-in fade-in duration-150"
        >
          <div className="flex items-center justify-between gap-2 mb-2 pb-2 border-b border-outline-variant">
            <span className="font-label-caps text-[10px] text-on-surface-variant uppercase tracking-wider">
              Wallet Node
            </span>
            {hoveredNode.isSanctioned ? (
              <span className="bg-error text-white text-[9px] font-bold px-2 py-0.5 rounded-full font-label-caps">
                SANCTIONED
              </span>
            ) : hoveredNode.label ? (
              <span className="bg-primary text-white text-[9px] font-bold px-2 py-0.5 rounded-full font-label-caps flex items-center gap-1">
                <span className="material-symbols-outlined text-[10px]">star</span>
                {hoveredNode.label}
              </span>
            ) : (
              <span className="text-on-surface-variant text-[10px] font-address-md">
                Active Node
              </span>
            )}
          </div>
          <p className="font-address-md text-xs text-on-surface break-all mb-3 select-all font-semibold">
            {hoveredNode.address}
          </p>
          {hoveredNode.isCapped && (
            <p className="text-[11px] text-[#B7791F] bg-[#F2A93B]/10 border border-[#F2A93B]/40 rounded p-2 mb-3 flex items-start gap-1.5">
              <span className="material-symbols-outlined text-[14px]">content_cut</span>
              <span>{capText}</span>
            </p>
          )}
          <WalletStats node={hoveredNode} />
        </div>
      )}

      {/* Small screens: wallet or line details in a draggable bottom sheet */}
      {compact && (
        <Sheet
          open={!!(selectedNode || selectedEdge)}
          onClose={() => {
            setSelectedNode(null);
            setSelectedEdge(null);
          }}
          title={selectedNode ? (selectedNode.label || 'Wallet') : 'Transactions on this line'}
          id="graph-detail-sheet"
        >
          {selectedNode && (
            <WalletSheetBody
              node={selectedNode}
              explorer={explorer}
              risk={riskFor(selectedNode.address)}
              sanction={sanctionFor(selectedNode.address)}
              capText={capText}
              onAddress={openAddressSheet}
            />
          )}
          {selectedEdge && <EdgeSheetBody edge={selectedEdge} explorer={explorer} onAddress={openAddressSheet} />}
        </Sheet>
      )}

      {/* Selected Node Details Drawer */}
      {selectedNode && !hoveredNode && !compact && (
        <div className="absolute top-6 right-6 bg-surface border border-outline-variant rounded-xl p-4 shadow-2xl z-30 w-[22rem] max-w-[calc(100%-3rem)]">
          <div className="flex items-center justify-between gap-2 mb-2 pb-2 border-b border-outline-variant">
            <div className="flex items-center gap-1.5">
              <span className="material-symbols-outlined text-primary text-[18px]">account_balance_wallet</span>
              <span className="font-label-caps text-xs text-on-surface uppercase font-bold">
                Selected Address
              </span>
            </div>
            <button
              onClick={() => setSelectedNode(null)}
              className="text-on-surface-variant hover:text-on-surface"
            >
              <span className="material-symbols-outlined text-[16px]">close</span>
            </button>
          </div>
          <p className="font-address-md text-xs text-on-surface break-all mb-3 bg-surface-container p-2 rounded border border-outline-variant select-all">
            {selectedNode.address}
          </p>
          <WalletStats node={selectedNode} />
          <div className="mt-3 mb-3">
            <h4 className="font-label-caps text-[10px] uppercase text-on-surface-variant font-bold mb-1.5">
              Transactions in this graph ({selectedNode.txs.length})
            </h4>
            <ul className="max-h-48 overflow-y-auto flex flex-col divide-y divide-outline-variant/40 border border-outline-variant/50 rounded">
              {selectedNode.txs.map((t, idx) => (
                <li key={`${t.hash}-${t.direction}-${idx}`} className="flex items-center gap-2 px-2 py-1.5 text-[11px]">
                  <span
                    className={`material-symbols-outlined text-[14px] ${t.direction === 'out' ? 'text-error' : 'text-[#4C8C4A]'}`}
                    title={t.direction === 'out' ? 'Sent' : 'Received'}
                    aria-label={t.direction === 'out' ? 'Sent' : 'Received'}
                  >
                    {t.direction === 'out' ? 'call_made' : 'call_received'}
                  </span>
                  <span className="text-on-surface-variant font-mono whitespace-nowrap">{formatDate(t.timestamp)}</span>
                  <span className="flex-1 text-right font-mono font-semibold text-on-surface whitespace-nowrap">
                    {t.direction === 'out' ? '−' : '+'}{formatEth(t.value)}
                    {t.kind === 'internal' && <span className="ml-1 text-[9px] text-on-surface-variant">INT</span>}
                  </span>
                  {t.hash ? (
                    <a
                      href={`${explorer}/tx/${t.hash}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-mono text-primary hover:underline whitespace-nowrap"
                      title={t.hash}
                    >
                      {shortHash(t.hash)}
                    </a>
                  ) : (
                    <span className="text-on-surface-variant">—</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                navigator.clipboard.writeText(selectedNode.address);
              }}
              className="flex-1 py-1.5 px-3 bg-surface-container hover:bg-surface-variant text-on-surface font-label-caps text-[11px] uppercase rounded border border-outline-variant transition-colors flex items-center justify-center gap-1"
            >
              <span className="material-symbols-outlined text-[14px]">content_copy</span>
              Copy Address
            </button>
            <a
              href={`${explorer}/address/${selectedNode.address}`}
              target="_blank"
              rel="noopener noreferrer"
              className="py-1.5 px-3 bg-primary text-white font-label-caps text-[11px] uppercase rounded hover:bg-primary-container transition-colors flex items-center justify-center gap-1"
            >
              <span className="material-symbols-outlined text-[14px]">open_in_new</span>
              Explorer
            </a>
          </div>
        </div>
      )}
    </div>
  );
};

// Copy button that confirms in place.
const CopyChip = ({ text, label = 'Copy' }) => {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        if (await copyText(text)) {
          setDone(true);
          setTimeout(() => setDone(false), 1500);
        }
      }}
      className="flex-1 rounded-lg border border-outline-variant bg-surface-container text-on-surface font-label-caps text-xs uppercase font-bold flex items-center justify-center gap-1.5"
    >
      <span className="material-symbols-outlined text-[18px]">{done ? 'check' : 'content_copy'}</span>
      {done ? 'Copied' : label}
    </button>
  );
};

// Transactions as tappable rows: date, signed amount, hash (opens the explorer).
const TxList = ({ txs, explorer, directional = true }) => (
  <ul className="flex flex-col divide-y divide-outline-variant/40 border border-outline-variant/50 rounded-lg">
    {txs.map((t, idx) => (
      <li key={`${t.hash}-${t.direction}-${idx}`} className="flex items-center gap-2 px-2.5 min-h-[48px] text-[13px]">
        {directional && (
          <span
            className={`material-symbols-outlined text-[18px] ${t.direction === 'out' ? 'text-error' : 'text-[#4C8C4A]'}`}
            aria-label={t.direction === 'out' ? 'Sent' : 'Received'}
          >
            {t.direction === 'out' ? 'call_made' : 'call_received'}
          </span>
        )}
        <span className="flex-1 min-w-0">
          <span className="block font-mono font-semibold text-on-surface">
            {directional ? (t.direction === 'out' ? '−' : '+') : ''}
            {formatEth(t.value)}
            {t.kind === 'internal' && <span className="ml-1 text-[10px] text-on-surface-variant">INT</span>}
          </span>
          <span className="block font-mono text-[11px] text-on-surface-variant">{formatDate(t.timestamp)}</span>
        </span>
        {t.hash ? (
          <a
            href={`${explorer}/tx/${t.hash}`}
            target="_blank"
            rel="noopener noreferrer"
            className="bt-tap flex items-center gap-1 font-mono text-[12px] text-primary px-1"
            title={t.hash}
          >
            {midTruncate(t.hash, 8, 4)}
            <span className="material-symbols-outlined text-[14px]">open_in_new</span>
          </a>
        ) : (
          <span className="text-on-surface-variant">—</span>
        )}
      </li>
    ))}
  </ul>
);

const WalletSheetBody = ({ node, explorer, risk, sanction, capText, onAddress }) => (
  <div className="flex flex-col gap-3 text-on-surface">
    <div className="flex items-center gap-2 flex-wrap">
      {node.isSanctioned && (
        <span className="bg-error text-white text-[11px] font-bold px-2 py-0.5 rounded-full font-label-caps">SANCTIONED</span>
      )}
      {risk && (
        <span className="bg-primary/10 text-primary border border-primary/30 text-[11px] font-bold px-2 py-0.5 rounded-full font-label-caps uppercase">
          {risk.tier} · {risk.score} {risk.score === 1 ? 'signal' : 'signals'}
        </span>
      )}
      {node.isCapped && (
        <span className="bg-[#F2A93B]/15 text-[#9c5a00] border border-[#F2A93B]/50 text-[11px] font-bold px-2 py-0.5 rounded-full font-label-caps">
          CAP REACHED
        </span>
      )}
    </div>
    <button
      type="button"
      onClick={() => onAddress(node.address, node.label || 'Wallet address')}
      className="w-full text-left font-mono text-[15px] bg-surface-container rounded-lg px-3 border border-outline-variant flex items-center justify-between gap-2"
      title={node.address}
    >
      <span>{midTruncate(node.address)}</span>
      <span className="text-[11px] font-sans text-on-surface-variant">Full address</span>
    </button>
    <div className="flex gap-2">
      <CopyChip text={node.address} label="Copy address" />
      <a
        href={`${explorer}/address/${node.address}`}
        target="_blank"
        rel="noopener noreferrer"
        className="bt-tap flex-1 rounded-lg bg-primary text-white font-label-caps text-xs uppercase font-bold flex items-center justify-center gap-1.5"
      >
        <span className="material-symbols-outlined text-[18px]">open_in_new</span>
        Explorer
      </a>
    </div>
    {sanction && (
      <div className="rounded-lg border border-error/40 bg-error/5 p-3">
        <p className="font-label-caps text-[11px] uppercase font-bold text-error mb-0.5">Sanctions match</p>
        <p className="text-sm font-semibold">{sanction.name}</p>
        <p className="text-xs text-on-surface-variant">Authority: {sanction.authority}</p>
        {sanction.note && <p className="text-xs text-on-surface-variant italic mt-1">{sanction.note}</p>}
      </div>
    )}
    {node.isCapped && <p className="text-xs text-[#9c5a00] bg-[#F2A93B]/10 border border-[#F2A93B]/40 rounded-lg p-2.5">{capText}</p>}
    <WalletStats node={node} />
    <div>
      <p className="font-label-caps text-[11px] uppercase text-on-surface-variant font-bold mb-1.5">Signals</p>
      {risk?.signals?.length ? (
        <div className="flex flex-wrap gap-1.5">
          {risk.signals.map((s) => (
            <span key={s} className="text-xs px-2 py-1 rounded bg-surface-container border border-outline-variant/50">{s}</span>
          ))}
        </div>
      ) : (
        <p className="text-xs text-on-surface-variant italic">No heuristic signals on this wallet.</p>
      )}
    </div>
    <div>
      <p className="font-label-caps text-[11px] uppercase text-on-surface-variant font-bold mb-1.5">
        Transactions in this graph ({node.txs.length})
      </p>
      <TxList txs={node.txs} explorer={explorer} />
    </div>
  </div>
);

const EdgeSheetBody = ({ edge, explorer, onAddress }) => {
  const from = typeof edge.source === 'object' ? edge.source : { address: edge.source };
  const to = typeof edge.target === 'object' ? edge.target : { address: edge.target };
  return (
    <div className="flex flex-col gap-3 text-on-surface">
      <div className="grid grid-cols-[auto,1fr] items-center gap-x-2 gap-y-1 text-sm">
        <span className="text-on-surface-variant text-xs font-label-caps uppercase font-bold">From</span>
        <button type="button" onClick={() => onAddress(from.address, from.label || 'Sender')} className="text-left font-mono" title={from.address}>
          {from.label ? `${from.label} · ` : ''}{midTruncate(from.address)}
        </button>
        <span className="text-on-surface-variant text-xs font-label-caps uppercase font-bold">To</span>
        <button type="button" onClick={() => onAddress(to.address, to.label || 'Recipient')} className="text-left font-mono" title={to.address}>
          {to.label ? `${to.label} · ` : ''}{midTruncate(to.address)}
        </button>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="bg-surface-container p-2 rounded">
          <span className="text-[10px] text-on-surface-variant block uppercase font-label-caps">Transactions</span>
          <span className="font-address-md font-bold text-primary">{edge.count}</span>
        </div>
        <div className="bg-surface-container p-2 rounded">
          <span className="text-[10px] text-on-surface-variant block uppercase font-label-caps">Total</span>
          <span className="font-address-md font-bold text-on-surface">{formatEth(edge.value)}</span>
        </div>
      </div>
      <TxList txs={edge.txs} explorer={explorer} directional={false} />
    </div>
  );
};

// Sent and received are shown separately: adding them would double-count money that
// merely passed through the wallet.
const WalletStats = ({ node }) => (
  <div className="grid grid-cols-2 gap-2 text-xs">
    <div className="bg-surface-container p-2 rounded">
      <span className="text-[10px] text-on-surface-variant block uppercase font-label-caps">Sent</span>
      <span className="font-address-md font-bold text-on-surface">{formatEth(node.sentTotal)}</span>
    </div>
    <div className="bg-surface-container p-2 rounded">
      <span className="text-[10px] text-on-surface-variant block uppercase font-label-caps">Received</span>
      <span className="font-address-md font-bold text-on-surface">{formatEth(node.receivedTotal)}</span>
    </div>
    <div className="bg-surface-container p-2 rounded">
      <span className="text-[10px] text-on-surface-variant block uppercase font-label-caps">Transactions</span>
      <span className="font-address-md font-bold text-primary">{node.txs.length}</span>
    </div>
    <div className="bg-surface-container p-2 rounded">
      <span className="text-[10px] text-on-surface-variant block uppercase font-label-caps">First / last seen</span>
      <span className="font-address-md text-[10px] text-on-surface block">{formatDate(node.firstSeen)}</span>
      <span className="font-address-md text-[10px] text-on-surface block">{formatDate(node.lastSeen)}</span>
    </div>
  </div>
);
