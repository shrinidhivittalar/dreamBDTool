// Inches are the source of truth for every position/dimension in the hamper
// layout. Pixels are a derived, render-only unit — never store or compare
// positions in pixels, only convert to pixels at the point of drawing.

export const DEFAULT_PX_PER_INCH = 40;

export function inchesToPx(inches, pxPerInch = DEFAULT_PX_PER_INCH) {
  return inches * pxPerInch;
}

// Rectangle corner (xIn, yIn) + widthIn/heightIn, converted to a px rect.
export function rectToPx({ xIn, yIn, widthIn, heightIn }, pxPerInch = DEFAULT_PX_PER_INCH) {
  return {
    x: inchesToPx(xIn, pxPerInch),
    y: inchesToPx(yIn, pxPerInch),
    width: inchesToPx(widthIn, pxPerInch),
    height: inchesToPx(heightIn, pxPerInch),
  };
}

// Regular hexagon defined by its point-to-point measurement: the distance
// between two opposite outer corners (the hexagon's long diagonal), not its
// flat-to-flat width. For a regular hexagon, point-to-point = 2 * circumradius.
//
// Vertices are computed in inches around (centerXIn, centerYIn) and only
// converted to px for rendering — pointToPointIn is the one true dimension;
// everything else (radius, vertex coordinates) is derived from it.
export function hexagonVerticesIn({ centerXIn, centerYIn, pointToPointIn, rotationDeg = 0 }) {
  const radiusIn = pointToPointIn / 2;
  const vertices = [];
  for (let i = 0; i < 6; i += 1) {
    const angleDeg = rotationDeg + i * 60;
    const angleRad = (Math.PI / 180) * angleDeg;
    vertices.push({
      xIn: centerXIn + radiusIn * Math.cos(angleRad),
      yIn: centerYIn + radiusIn * Math.sin(angleRad),
    });
  }
  return vertices;
}

export function hexagonPointsAttr(hexParams, pxPerInch = DEFAULT_PX_PER_INCH) {
  return hexagonVerticesIn(hexParams)
    .map(({ xIn, yIn }) => `${inchesToPx(xIn, pxPerInch)},${inchesToPx(yIn, pxPerInch)}`)
    .join(' ');
}
