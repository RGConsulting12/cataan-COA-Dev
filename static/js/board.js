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

  const HEX_SIZE = 42;

  function hexIndex(hexId) {
    const match = /(\d+)/.exec(hexId);
    return match ? parseInt(match[1], 10) - 1 : 0;
  }

  function layoutHexCenters(hexes) {
    const positions = {};
    const layouts = [
      [0, 0],
      [1, 0],
      [2, 0],
      [0.5, 0.87],
      [1.5, 0.87],
      [2.5, 0.87],
      [0, 1.74],
      [1, 1.74],
      [2, 1.74],
      [0.5, 2.61],
      [1.5, 2.61],
      [2.5, 2.61],
      [1, 3.48],
      [2, 3.48],
      [1.5, 4.35],
      [2.5, 4.35],
      [2, 5.22],
      [3, 5.22],
      [2.5, 6.09],
    ];
    hexes.forEach((hex, i) => {
      const idx = hexIndex(hex.id);
      const [col, row] = layouts[idx] || [i % 3, Math.floor(i / 3)];
      const x = 120 + col * HEX_SIZE * 1.75;
      const y = 80 + row * HEX_SIZE * 1.5;
      positions[hex.id] = { x, y };
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
    const angle = (parseInt(vertex.id.replace(/\D/g, ""), 10) || 0) * 1.2;
    return {
      x: cx + Math.cos(angle) * HEX_SIZE * 0.85,
      y: cy + Math.sin(angle) * HEX_SIZE * 0.85,
    };
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
