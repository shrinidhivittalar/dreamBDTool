import { inchesToPx, rectToPx, hexagonPointsAttr, DEFAULT_PX_PER_INCH } from './geometry';

// Renders the outer hamper boundary plus its internal products, all defined
// in inches (the coordinate system's real-world unit) and only converted to
// pixels here at draw time. Nothing upstream of this component should ever
// deal in pixels.
//
// `hamperWidthIn` / `hamperHeightIn` define the coordinate space itself.
// Each product is one of:
//   { shape: 'rect', xIn, yIn, widthIn, heightIn, label }
//   { shape: 'hexagon', centerXIn, centerYIn, pointToPointIn, rotationDeg, label }
//
// A hexagon's pointToPointIn is caller-supplied, not hardcoded here — the
// relationship "hexagon point-to-point == hamper width" is expressed by the
// caller passing pointToPointIn: hamperWidthIn (see demo below), so resizing
// the hamper automatically resizes the hexagon.
export default function HamperLayoutCanvas({
  hamperWidthIn,
  hamperHeightIn,
  products = [],
  pxPerInch = DEFAULT_PX_PER_INCH,
  children,
}) {
  const widthPx = inchesToPx(hamperWidthIn, pxPerInch);
  const heightPx = inchesToPx(hamperHeightIn, pxPerInch);

  return (
    <svg
      className="hamper-layout-canvas"
      width={widthPx}
      height={heightPx}
      viewBox={`0 0 ${widthPx} ${heightPx}`}
      style={{ overflow: 'visible' }}
      role="img"
      aria-label={`Hamper layout, ${hamperWidthIn} by ${hamperHeightIn} inches`}
    >
      <rect
        className="hamper-layout-boundary"
        x={0}
        y={0}
        width={widthPx}
        height={heightPx}
        fill="none"
        stroke="currentColor"
      />

      {products.map((product, index) => {
        const key = product.id ?? index;

        if (product.shape === 'hexagon') {
          return (
            <polygon
              key={key}
              className="hamper-layout-product hamper-layout-product-hexagon"
              fill="#d9c9a3"
              stroke="#7a6a45"
              points={hexagonPointsAttr(
                {
                  centerXIn: product.centerXIn,
                  centerYIn: product.centerYIn,
                  pointToPointIn: product.pointToPointIn,
                  rotationDeg: product.rotationDeg ?? 0,
                },
                pxPerInch
              )}
            >
              {product.label ? <title>{product.label}</title> : null}
            </polygon>
          );
        }

        const { x, y, width, height } = rectToPx(product, pxPerInch);
        return (
          <rect
            key={key}
            className="hamper-layout-product hamper-layout-product-rect"
            x={x}
            y={y}
            width={width}
            height={height}
          >
            {product.label ? <title>{product.label}</title> : null}
          </rect>
        );
      })}

      {/* Optional generic overlay slot (e.g. dimension/measurement
          annotations) — kept out of the core canvas so this component stays
          a pure coordinate-to-pixel renderer with no annotation logic. */}
      {children}
    </svg>
  );
}
