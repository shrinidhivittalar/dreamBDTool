import csv
from io import BytesIO, StringIO
from textwrap import wrap

try:
    from openpyxl import Workbook
except ImportError:  # pragma: no cover - exercised only when optional dependency is absent
    Workbook = None

try:
    from .models import Recommendation
except ImportError:
    from models import Recommendation


EXPORT_COLUMNS = [
    "option",
    "products",
    "vendors",
    "total_price",
    "dad_selling_price",
    "rock_bottom_price",
    "customization_surcharge",
    "packaging_cost",
    "discount",
    "remaining_budget",
    "packaging",
]

CONTENT_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}

FILE_EXTENSIONS = {"csv": "csv", "xlsx": "xlsx", "pdf": "pdf"}

ITEMIZED_COLUMNS = [
    "option",
    "product",
    "vendor",
    "category",
    "dad_selling_price",
    "rock_bottom_price",
    "option_total_price",
]


def itemized_rows(recommendations: list[Recommendation]) -> list[dict[str, object]]:
    """One row per product, per option - for pasting straight into a quote sheet."""
    rows: list[dict[str, object]] = []
    for index, recommendation in enumerate(recommendations, start=1):
        for product in recommendation.products:
            rows.append({
                "option": index,
                "product": product.name,
                "vendor": product.vendor,
                "category": product.category,
                "dad_selling_price": product.selling_price,
                "rock_bottom_price": product.rock_bottom_price if product.rock_bottom_price is not None else product.selling_price,
                "option_total_price": recommendation.total_price,
            })
    return rows


def recommendation_rows(recommendations: list[Recommendation]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, recommendation in enumerate(recommendations, start=1):
        rows.append({
            "option": index,
            "products": ", ".join(product.name for product in recommendation.products),
            "vendors": ", ".join(dict.fromkeys(product.vendor for product in recommendation.products if product.vendor)),
            "total_price": recommendation.total_price,
            "dad_selling_price": recommendation.dad_selling_price,
            "rock_bottom_price": recommendation.rock_bottom_price,
            "customization_surcharge": recommendation.customization_surcharge,
            "packaging_cost": recommendation.packaging_cost,
            "discount": recommendation.discount,
            "remaining_budget": recommendation.remaining_budget,
            "packaging": ", ".join(item.name for item in recommendation.packaging),
        })
    return rows


def export_csv(recommendations: list[Recommendation], layout: str = "summary") -> bytes:
    columns = ITEMIZED_COLUMNS if layout == "itemized" else EXPORT_COLUMNS
    rows = itemized_rows(recommendations) if layout == "itemized" else recommendation_rows(recommendations)
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def export_xlsx(recommendations: list[Recommendation], layout: str = "summary") -> bytes:
    if Workbook is None:
        raise RuntimeError("Excel export requires openpyxl")
    columns = ITEMIZED_COLUMNS if layout == "itemized" else EXPORT_COLUMNS
    rows = itemized_rows(recommendations) if layout == "itemized" else recommendation_rows(recommendations)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Itemized" if layout == "itemized" else "Recommendations"
    sheet.append(columns)
    for row in rows:
        sheet.append([row[column] for column in columns])
    for column_cells in sheet.columns:
        width = max(len(str(cell.value or "")) for cell in column_cells)
        sheet.column_dimensions[column_cells[0].column_letter].width = min(max(width + 2, 12), 48)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_text_lines(recommendations: list[Recommendation]) -> list[str]:
    lines = ["Dream a Dozen Recommendation Quote", ""]
    for index, recommendation in enumerate(recommendations, start=1):
        lines.append(f"Option {index}")
        lines.append(f"Products: {', '.join(product.name for product in recommendation.products)}")
        lines.append(f"Total price: INR {recommendation.total_price}")
        lines.append(f"DaD selling price: INR {recommendation.dad_selling_price}")
        lines.append(f"Rock bottom price: INR {recommendation.rock_bottom_price}")
        if recommendation.packaging:
            lines.append(f"Packaging: {', '.join(item.name for item in recommendation.packaging)}")
        lines.append("")
    wrapped: list[str] = []
    for line in lines:
        wrapped.extend(wrap(line, width=92) or [""])
    return wrapped


def export_pdf(recommendations: list[Recommendation]) -> bytes:
    lines = _pdf_text_lines(recommendations)
    y = 760
    content_lines = ["BT", "/F1 10 Tf", "50 760 Td"]
    first = True
    for line in lines[:46]:
        if first:
            first = False
        else:
            content_lines.append("0 -15 Td")
        content_lines.append(f"({_pdf_escape(line)}) Tj")
    content_lines.append("ET")
    content = "\n".join(content_lines).encode("latin-1", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"\nendstream",
    ]
    output = BytesIO()
    output.write(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(output.tell())
        output.write(f"{index} 0 obj\n".encode("ascii"))
        output.write(obj)
        output.write(b"\nendobj\n")
    xref = output.tell()
    output.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    return output.getvalue()


def export_recommendations(recommendations: list[Recommendation], export_format: str, layout: str = "summary") -> bytes:
    normalized = export_format.lower()
    if layout not in {"summary", "itemized"}:
        raise ValueError(f"Unsupported export layout: {layout}")
    if normalized == "csv":
        return export_csv(recommendations, layout)
    if normalized in {"xlsx", "excel"}:
        return export_xlsx(recommendations, layout)
    if normalized == "pdf":
        return export_pdf(recommendations)
    raise ValueError(f"Unsupported export format: {export_format}")


def content_type_for(export_format: str) -> str:
    normalized = "xlsx" if export_format.lower() == "excel" else export_format.lower()
    return CONTENT_TYPES[normalized]


def filename_for(export_format: str) -> str:
    normalized = "xlsx" if export_format.lower() == "excel" else export_format.lower()
    return f"dream-a-dozen-recommendations.{FILE_EXTENSIONS[normalized]}"
