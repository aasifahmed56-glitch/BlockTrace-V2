import React, { useEffect, useRef, useState, useMemo } from 'react';
import * as d3 from 'd3';
import { useInvestigation } from '../context/InvestigationContext';

export const GraphCanvas = ({ filterQuery = '', onSelectWallet }) => {
  const {
    edges,
    activePathEdges,
    sanctions,
    entityLabels,
    isLoadingGraph,
    limitedWallets,
    traceScope,
  } = useInvestigation();

  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [zoomTransform, setZoomTransform] = useState(null);

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

  // Derive unique nodes from filtered edges
  const { nodes, links } = useMemo(() => {
    const nodeMap = new Map();

    filteredEdges.forEach((e) => {
      if (!nodeMap.has(e.from)) {
        const fromLower = e.from.toLowerCase();
        nodeMap.set(e.from, {
          id: e.from,
          address: e.from,
          isSanctioned: sanctionedSet.has(fromLower),
          isCapped: cappedSet.has(fromLower),
          label: entityLabels[fromLower] || null,
          inDegree: 0,
          outDegree: 0,
          totalValue: 0,
        });
      }
      if (!nodeMap.has(e.to)) {
        const toLower = e.to.toLowerCase();
        nodeMap.set(e.to, {
          id: e.to,
          address: e.to,
          isSanctioned: sanctionedSet.has(toLower),
          isCapped: cappedSet.has(toLower),
          label: entityLabels[toLower] || null,
          inDegree: 0,
          outDegree: 0,
          totalValue: 0,
        });
      }

      const fromNode = nodeMap.get(e.from);
      const toNode = nodeMap.get(e.to);
      fromNode.outDegree += 1;
      toNode.inDegree += 1;
      fromNode.totalValue += Number(e.value || 0);
      toNode.totalValue += Number(e.value || 0);
    });

    const linksArray = filteredEdges.map((e, index) => ({
      id: `${e.from}-${e.to}-${index}`,
      source: e.from,
      target: e.to,
      value: Number(e.value || 0),
    }));

    return {
      nodes: Array.from(nodeMap.values()),
      links: linksArray,
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

    // Zoom behavior
    const zoom = d3
      .zoom()
      .scaleExtent([0.15, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
        setZoomTransform(event.transform);
      });

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

    // Render Link Value Labels (visible on higher zoom)
    const linkText = g
      .append('g')
      .attr('class', 'link-labels')
      .selectAll('text')
      .data(links)
      .enter()
      .append('text')
      .attr('font-family', 'JetBrains Mono')
      .attr('font-size', '9px')
      .attr('fill', '#eed5cb')
      .attr('text-anchor', 'middle')
      .text((d) => (d.value > 0 ? `${d.value >= 1 ? d.value.toFixed(2) : d.value.toFixed(4)} ETH` : ''));

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
      .text((d) => (d.label ? `${d.label} (${truncate(d.address)})` : truncate(d.address)));

    // Interactions
    node
      .on('mouseenter', (event, d) => {
        setHoveredNode(d);
        d3.select(event.currentTarget).select('circle.node-core').attr('stroke', '#ffffff').attr('stroke-width', 3.5);
      })
      .on('mouseleave', (event, d) => {
        setHoveredNode(null);
        d3.select(event.currentTarget)
          .select('circle.node-core')
          .attr('stroke', d.isSanctioned ? '#ffdad6' : d.label ? '#ffdbcd' : '#e1bfb2')
          .attr('stroke-width', 2.5);
      })
      .on('click', (event, d) => {
        event.stopPropagation();
        setSelectedNode(d);
        if (onSelectWallet) {
          onSelectWallet(d.address);
        }
      });

    svg.on('click', () => {
      setSelectedNode(null);
    });

    // Simulation Tick Updates
    simulation.on('tick', () => {
      link
        .attr('x1', (d) => d.source.x)
        .attr('y1', (d) => d.source.y)
        .attr('x2', (d) => d.target.x)
        .attr('y2', (d) => d.target.y);

      linkText
        .attr('x', (d) => (d.source.x + d.target.x) / 2)
        .attr('y', (d) => (d.source.y + d.target.y) / 2 - 4);

      node.attr('transform', (d) => `translate(${d.x},${d.y})`);
    });

    return () => {
      simulation.stop();
    };
  }, [nodes, links, sanctionedSet, onSelectWallet, capText]);

  // Zoom Controls
  const handleZoom = (scaleFactor) => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.transition().duration(300).call(d3.zoom().scaleBy, scaleFactor);
  };

  const handleResetZoom = () => {
    if (!svgRef.current || !containerRef.current) return;
    const width = containerRef.current.clientWidth || 800;
    const height = containerRef.current.clientHeight || 600;
    const svg = d3.select(svgRef.current);
    svg
      .transition()
      .duration(400)
      .call(d3.zoom().transform, d3.zoomIdentity.translate(width / 2, height / 2).scale(0.85));
  };

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
      <div className="absolute bottom-6 right-6 flex items-center gap-1 bg-surface/90 backdrop-blur-md p-1.5 rounded-lg border border-outline-variant shadow-xl z-20">
        <button
          onClick={() => handleZoom(1.3)}
          className="p-2 text-on-surface hover:text-primary hover:bg-surface-container rounded transition-colors"
          title="Zoom In"
        >
          <span className="material-symbols-outlined text-[18px]">add</span>
        </button>
        <button
          onClick={() => handleZoom(0.7)}
          className="p-2 text-on-surface hover:text-primary hover:bg-surface-container rounded transition-colors"
          title="Zoom Out"
        >
          <span className="material-symbols-outlined text-[18px]">remove</span>
        </button>
        <div className="w-[1px] h-4 bg-outline-variant mx-1" />
        <button
          onClick={handleResetZoom}
          className="p-2 text-on-surface hover:text-primary hover:bg-surface-container rounded transition-colors"
          title="Fit to Screen"
        >
          <span className="material-symbols-outlined text-[18px]">center_focus_strong</span>
        </button>
      </div>

      {/* Legend Overlay */}
      <div className="absolute bottom-6 left-6 bg-surface/90 backdrop-blur-md px-4 py-3 rounded-lg border border-outline-variant shadow-xl z-20 flex flex-wrap items-center gap-4 text-xs font-label-caps uppercase text-on-surface">
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
      {hoveredNode && (
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
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="bg-surface-container p-2 rounded">
              <span className="text-[10px] text-on-surface-variant block uppercase font-label-caps">Connections</span>
              <span className="font-address-md font-bold text-on-surface">
                {hoveredNode.inDegree + hoveredNode.outDegree} txs
              </span>
            </div>
            <div className="bg-surface-container p-2 rounded">
              <span className="text-[10px] text-on-surface-variant block uppercase font-label-caps">Volume</span>
              <span className="font-address-md font-bold text-primary">
                {hoveredNode.totalValue.toFixed(2)} ETH
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Selected Node Details Drawer */}
      {selectedNode && !hoveredNode && (
        <div className="absolute top-6 right-6 bg-surface border border-outline-variant rounded-xl p-4 shadow-2xl z-30 max-w-sm">
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
          <p className="font-address-md text-xs text-on-surface break-all mb-4 bg-surface-container p-2 rounded border border-outline-variant select-all">
            {selectedNode.address}
          </p>
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
              href={`https://etherscan.io/address/${selectedNode.address}`}
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
