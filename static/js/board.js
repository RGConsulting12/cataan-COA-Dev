/**
 * Render Catan board state as SVG (hexes, robber, settlements, cities, roads).
 */
(function () {
  const TERRAIN_COLORS = {
    forest: "#2d6a4f",
    hills: "#c45c26",
    pasture: "#95d5b2",
    fields: "#f4d35e",
    mountains: "#6c757d",
    desert: "#e9c46a",
  };

  const PLAYER_COLORS = {
    red: "#c1121f",
    blue: "#1d3557",
    orange: "#e76f51",
    white: "#f1faee",
    green: "#2a9d8f",
    brown: "#6f4e37",
  };

  const HEX_SIZE = 38;
  const HEX_WIDTH = HEX_SIZE * 2;
  const HEX_HEIGHT = HEX_SIZE * Math.sqrt(3);
  const HORIZ_SPACING = HEX_WIDTH * 0.75;
  const VERT_SPACING = HEX_HEIGHT;

  function hexIndex(hexId) {
    const match = /(\d+)/.exec(hexId);
    return match ? parseInt(match[1], 10) - 1 : 0;
  }

  function layoutHexCenters(hexes) {
    const positions = {};
    const rowConfig = [3, 4, 5, 4, 3];
    const rowOffsets = [1, 0.5, 0, 0.5, 1];
    
    let hexIdx = 0;
    const centerX = 300;
    const startY = 70;
    
    for (let row = 0; row < rowConfig.length; row++) {
      const hexesInRow = rowConfig[row];
      const rowOffset = rowOffsets[row];
      const y = startY + row * VERT_SPACING * 0.87;
      
      for (let col = 0; col < hexesInRow; col++) {
        const x = centerX + (col - (hexesInRow - 1) / 2) * HORIZ_SPACING;
        const expectedId = `h${hexIdx + 1}`;
        positions[expectedId] = { x, y };
        hexIdx++;
      }
    }
    
    hexes.forEach((hex) => {
      if (positions[hex.id]) return;
      
      if (hex.row !== undefined && hex.col !== undefined) {
        const row = hex.row;
        const hexesInRow = rowConfig[row] || 5;
        const y = startY + row * VERT_SPACING * 0.87;
        const x = centerX + (hex.col - (hexesInRow - 1) / 2) * HORIZ_SPACING;
        positions[hex.id] = { x, y };
      } else {
        const idx = hexIndex(hex.id);
        let cumulative = 0;
        for (let r = 0; r < rowConfig.length; r++) {
          if (idx < cumulative + rowConfig[r]) {
            const col = idx - cumulative;
            const hexesInRow = rowConfig[r];
            const y = startY + r * VERT_SPACING * 0.87;
            const x = centerX + (col - (hexesInRow - 1) / 2) * HORIZ_SPACING;
            positions[hex.id] = { x, y };
            break;
          }
          cumulative += rowConfig[r];
        }
      }
    });
    
    return positions;
  }

  function hexPoints(cx, cy, size) {
    const points = [];
    for (let i = 0; i < 6; i++) {
      const angle = (Math.PI / 180) * (60 * i - 30);
      points.push(`${cx + size * Math.cos(angle)},${cy + size * Math.sin(angle)}`);
    }
    return points.join(" ");
  }

  function vertexPosition(vertex, hexPositions) {
    const refs = vertex.hexes || [];
    let x = 0;
    let y = 0;
    let count = 0;
    refs.forEach((hid) => {
      const pos = hexPositions[hid];
      if (pos) {
        x += pos.x;
        y += pos.y;
        count += 1;
      }
    });
    if (!count) {
      const n = parseInt((vertex.id.match(/\d+/) || ["0"])[0], 10);
      return { x: 300 + (n % 5) * 30, y: 250 + Math.floor(n / 5) * 30 };
    }
    const cx = x / count;
    const cy = y / count;
    
    if (count === 1) {
      const vid = parseInt(vertex.id.replace(/\D/g, ""), 10) || 0;
      const angle = (vid * 1.05) + Math.PI / 6;
      return {
        x: cx + Math.cos(angle) * HEX_SIZE,
        y: cy + Math.sin(angle) * HEX_SIZE,
      };
    }
    
    if (count === 2) {
      const vid = parseInt(vertex.id.replace(/\D/g, ""), 10) || 0;
      const angle = (vid * 0.9) + Math.PI / 4;
      return {
        x: cx + Math.cos(angle) * HEX_SIZE * 0.6,
        y: cy + Math.sin(angle) * HEX_SIZE * 0.6,
      };
    }
    
    return { x: cx, y: cy };
  }

  function svgEl(tag, attrs) {
    const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.entries(attrs || {}).forEach(([k, v]) => el.setAttribute(k, v));
    return el;
  }

  function renderBoard(svg, state) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);

    const board = state.board || { hexes: [], vertices: [], edges: [] };
    const hexPositions = layoutHexCenters(board.hexes || []);

    (board.hexes || []).forEach((hex) => {
      const pos = hexPositions[hex.id];
      if (!pos) return;
      const fill = TERRAIN_COLORS[hex.terrain] || "#bbb";
      const polygon = svgEl("polygon", {
        points: hexPoints(pos.x, pos.y, HEX_SIZE),
        fill,
        stroke: hex.robber ? "#111" : "#5c4d3c",
        "stroke-width": hex.robber ? "4" : "1.5",
      });
      if (hex.robber) {
        polygon.setAttribute("class", "robber-hex");
      }
      svg.appendChild(polygon);

      if (hex.number != null) {
        const label = svgEl("text", {
          x: String(pos.x),
          y: String(pos.y + 5),
          "text-anchor": "middle",
          fill: hex.number === 6 || hex.number === 8 ? "#8b0000" : "#222",
          "font-size": "16",
          "font-weight": "bold",
        });
        label.textContent = String(hex.number);
        svg.appendChild(label);
      }

      if (hex.robber) {
        const robber = svgEl("circle", {
          cx: String(pos.x),
          cy: String(pos.y - 18),
          r: "10",
          fill: "#222",
        });
        svg.appendChild(robber);
      }
    });

    const vertexPositions = {};
    (board.vertices || []).forEach((v) => {
      vertexPositions[v.id] = vertexPosition(v, hexPositions);
    });

    (board.edges || []).forEach((edge) => {
      const verts = edge.vertices || [];
      if (verts.length < 2) return;
      const a = vertexPositions[verts[0]];
      const b = vertexPositions[verts[1]];
      if (!a || !b) return;
      const color = edge.owner ? PLAYER_COLORS[edge.owner] || "#666" : "transparent";
      if (edge.owner) {
        svg.appendChild(
          svgEl("line", {
            x1: String(a.x),
            y1: String(a.y),
            x2: String(b.x),
            y2: String(b.y),
            stroke: color,
            "stroke-width": "6",
            "stroke-linecap": "round",
          })
        );
      }
    });

    (board.vertices || []).forEach((v) => {
      if (!v.owner || !v.building) return;
      const pos = vertexPositions[v.id];
      if (!pos) return;
      const color = PLAYER_COLORS[v.owner] || "#333";
      if (v.building === "city") {
        svg.appendChild(
          svgEl("rect", {
            x: String(pos.x - 10),
            y: String(pos.y - 10),
            width: "20",
            height: "20",
            fill: color,
            stroke: "#111",
            "stroke-width": "1",
          })
        );
      } else {
        svg.appendChild(
          svgEl("circle", {
            cx: String(pos.x),
            cy: String(pos.y),
            r: "9",
            fill: color,
            stroke: "#111",
            "stroke-width": "1",
          })
        );
      }
    });
  }

  window.BoardRenderer = { renderBoard };
})();
