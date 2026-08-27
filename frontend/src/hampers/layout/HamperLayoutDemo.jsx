import HamperLayoutCanvas from './HamperLayoutCanvas';
import { inchesToPx, hexagonVerticesIn, DEFAULT_PX_PER_INCH } from './geometry';

// Standalone visual sanity-check for the coordinate system: a 10in x 7in
// hamper with ONE hexagon whose point-to-point measurement is dynamically
// bound to the hamper width (hexagonPointToPoint = hamperWidth).
//
// IMPORTANT: this demo intentionally covers only the single-hexagon,
// full-width case. It is NOT the final two-hexagon layout — the
// relationship between two hexagons and the 10in outer hamper is still
// undecided and will be defined after this screenshot is reviewed.
//
// Not wired into any existing flow — import and mount manually to preview.
export default function HamperLayoutDemo() {
  const hamperWidthIn = 10;
  const hamperHeightIn = 7;
  const pxPerInch = DEFAULT_PX_PER_INCH;

  const hexagon = {
    id: 'demo-hexagon',
    shape: 'hexagon',
    centerXIn: hamperWidthIn / 2,
    centerYIn: hamperHeightIn / 2,
    pointToPointIn: hamperWidthIn, // dynamic: tracks hamperWidthIn, never a literal
    rotationDeg: 0,
    label: 'Hexagonal product (point-to-point = hamper width)',
  };

  const products = [hexagon];

  // The two opposite corners the point-to-point measurement spans, for
  // rotationDeg 0: vertex 0 (angle 0deg, rightmost point) and vertex 3
  // (angle 180deg, leftmost point) — the hexagon's long horizontal diagonal.
  const vertices = hexagonVerticesIn(hexagon);
  const rightCorner = vertices[0];
  const leftCorner = vertices[3];

  const widthLabelY = inchesToPx(hamperHeightIn, pxPerInch) + 24;
  const heightLabelX = -28;
  const pointToPointLabelY = inchesToPx(hexagon.centerYIn, pxPerInch) - 12;

  return (
    <div style={{ padding: 48, fontFamily: 'sans-serif' }}>
      <div style={{ display: 'inline-block', position: 'relative', margin: 40 }}>
        <HamperLayoutCanvas
          hamperWidthIn={hamperWidthIn}
          hamperHeightIn={hamperHeightIn}
          products={products}
          pxPerInch={pxPerInch}
        >
          {/* Width dimension line (bottom) */}
          <g className="dim-width" stroke="#1a7f37" fill="#1a7f37">
            <line
              x1={0}
              y1={inchesToPx(hamperHeightIn, pxPerInch) + 12}
              x2={inchesToPx(hamperWidthIn, pxPerInch)}
              y2={inchesToPx(hamperHeightIn, pxPerInch) + 12}
              markerStart="url(#arrow)"
              markerEnd="url(#arrow)"
            />
            <text x={inchesToPx(hamperWidthIn, pxPerInch) / 2} y={widthLabelY} textAnchor="middle" stroke="none">
              hamper width = {hamperWidthIn} in
            </text>
          </g>

          {/* Height dimension line (left) */}
          <g className="dim-height" stroke="#1a56db" fill="#1a56db">
            <line
              x1={-12}
              y1={0}
              x2={-12}
              y2={inchesToPx(hamperHeightIn, pxPerInch)}
              markerStart="url(#arrow)"
              markerEnd="url(#arrow)"
            />
            <text
              x={heightLabelX}
              y={inchesToPx(hamperHeightIn, pxPerInch) / 2}
              textAnchor="middle"
              stroke="none"
              transform={`rotate(-90 ${heightLabelX} ${inchesToPx(hamperHeightIn, pxPerInch) / 2})`}
            >
              hamper height = {hamperHeightIn} in
            </text>
          </g>

          {/* Point-to-point measurement line across the hexagon's two
              opposite outer corners */}
          <g className="dim-point-to-point" stroke="#b42318" fill="#b42318">
            <line
              x1={inchesToPx(leftCorner.xIn, pxPerInch)}
              y1={inchesToPx(leftCorner.yIn, pxPerInch)}
              x2={inchesToPx(rightCorner.xIn, pxPerInch)}
              y2={inchesToPx(rightCorner.yIn, pxPerInch)}
              strokeDasharray="6 4"
              markerStart="url(#arrow-red)"
              markerEnd="url(#arrow-red)"
            />
            <circle cx={inchesToPx(leftCorner.xIn, pxPerInch)} cy={inchesToPx(leftCorner.yIn, pxPerInch)} r={5} />
            <circle cx={inchesToPx(rightCorner.xIn, pxPerInch)} cy={inchesToPx(rightCorner.yIn, pxPerInch)} r={5} />
            <text x={inchesToPx(hexagon.centerXIn, pxPerInch)} y={pointToPointLabelY} textAnchor="middle" stroke="none">
              point-to-point = {hexagon.pointToPointIn} in (= hamper width)
            </text>
          </g>

          <defs>
            <marker id="arrow" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" fill="#1a7f37" />
            </marker>
            <marker id="arrow-red" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" fill="#b42318" />
            </marker>
          </defs>
        </HamperLayoutCanvas>
      </div>
      <p style={{ maxWidth: 480 }}>
        Single hexagon, full hamper width only. This is <strong>not</strong> the two-hexagon
        layout — that relationship is still to be decided.
      </p>
    </div>
  );
}
