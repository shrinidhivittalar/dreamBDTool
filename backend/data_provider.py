import asyncio
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

try:
    from .catalog_loader import CatalogValidationReport, load_catalog, load_catalog_bytes, load_products
    from .models import Product
except ImportError:
    from catalog_loader import CatalogValidationReport, load_catalog, load_catalog_bytes, load_products
    from models import Product


ZOHO_SHEET_URL = "https://workdrive.zohoexternal.com/external/sheet/cd9f335d859f9900cca6de757af215f3b14ba7dab04c948144edc07892bb0e9e"
ZOHO_DOWNLOAD_URL = "https://workdrive.zohoexternal.com/external/cd9f335d859f9900cca6de757af215f3b14ba7dab04c948144edc07892bb0e9e/download?directDownload=true"
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOCAL_CATALOG = ROOT / "products.xlsx"
DEFAULT_FALLBACK_CATALOG = ROOT / "Input Data - Quotations Tool_Sheet1.csv"
DEFAULT_CACHE_PATH = ROOT / ".cache" / "products_catalog"


@dataclass(frozen=True)
class DataSyncStatus:
    product_count: int
    source_url: str
    cache_path: str
    current_source: str = "none"
    last_success_at: datetime | None = None
    last_attempt_at: datetime | None = None
    last_error: str | None = None
    using_cache: bool = False
    validation_warnings: list[str] | None = None

    @property
    def warning(self) -> str | None:
        if not self.last_error:
            return None
        if self.product_count:
            return f"Could not refresh product data. Using existing catalog. Last error: {self.last_error}"
        return f"Could not load product data and no cached catalog is available. Last error: {self.last_error}"

    def as_dict(self) -> dict[str, object]:
        return {
            "product_count": self.product_count,
            "source_url": self.source_url,
            "cache_path": self.cache_path,
            "current_source": self.current_source,
            "last_success_at": self.last_success_at.isoformat() if self.last_success_at else None,
            "last_attempt_at": self.last_attempt_at.isoformat() if self.last_attempt_at else None,
            "last_error": self.last_error,
            "using_cache": self.using_cache,
            "warning": self.warning,
            "validation_warnings": self.validation_warnings or [],
        }


class ProductDataProvider:
    """Owns product data synchronization and hides the backing source."""

    def __init__(
        self,
        source_url: str = ZOHO_DOWNLOAD_URL,
        cache_path: Path = DEFAULT_CACHE_PATH,
        local_catalog_path: Path | None = None,
        fallback_catalog_path: Path = DEFAULT_FALLBACK_CATALOG,
        timeout_seconds: int = 30,
    ) -> None:
        self.source_url = os.environ.get("PRODUCT_SHEET_URL", source_url)
        self.cache_path = Path(os.environ.get("PRODUCT_CACHE_PATH", str(cache_path)))
        configured_local = os.environ.get("PRODUCT_CATALOG_PATH")
        self.local_catalog_path = Path(configured_local) if configured_local else local_catalog_path
        self.fallback_catalog_path = Path(os.environ.get("PRODUCT_FALLBACK_CATALOG_PATH", str(fallback_catalog_path)))
        self.timeout_seconds = timeout_seconds
        self._products: list[Product] = []
        self._lock = threading.RLock()
        self._last_success_at: datetime | None = None
        self._last_attempt_at: datetime | None = None
        self._last_error: str | None = None
        self._using_cache = False
        self._current_source = "none"
        self._validation_report: CatalogValidationReport | None = None

    def load_initial(self) -> DataSyncStatus:
        for path in self._initial_paths():
            if not path.exists():
                continue
            try:
                return self.load_from_path(path)
            except Exception as error:
                with self._lock:
                    self._last_error = str(error)
                    self._last_attempt_at = datetime.now()
        if self.cache_path.exists():
            return self.load_cache()
        return self.get_status()

    def get_products(self) -> list[Product]:
        with self._lock:
            return list(self._products)

    def get_status(self) -> DataSyncStatus:
        with self._lock:
            return DataSyncStatus(
                product_count=len(self._products),
                source_url=self.source_url,
                cache_path=str(self.cache_path),
                current_source=self._current_source,
                last_success_at=self._last_success_at,
                last_attempt_at=self._last_attempt_at,
                last_error=self._last_error,
                using_cache=self._using_cache,
                validation_warnings=self._validation_report.warnings if self._validation_report else [],
            )

    def load_from_path(self, path: str | Path) -> DataSyncStatus:
        now = datetime.now()
        result = load_catalog(path)
        if not result.products:
            raise RuntimeError("Catalog did not contain any valid products")
        with self._lock:
            self._products = result.products
            self._validation_report = result.report
            self._last_attempt_at = now
            self._last_success_at = datetime.now()
            self._last_error = None
            self._using_cache = False
            self._current_source = str(path)
        return self.get_status()

    def refresh(self) -> DataSyncStatus:
        now = datetime.now()
        try:
            payload = self._download_latest()
            status = self.refresh_from_bytes(payload, filename="zoho_products.xlsx", cache=True)
            with self._lock:
                self._last_attempt_at = now
                self._current_source = self.source_url
            return status
        except Exception as error:
            self._load_cache_after_failure(str(error), now)
            return self.get_status()

    def refresh_from_bytes(self, payload: bytes, filename: str = "uploaded_catalog.xlsx", cache: bool = True) -> DataSyncStatus:
        now = datetime.now()
        result = load_catalog_bytes(payload, filename=filename)
        if not result.products:
            raise RuntimeError("Uploaded catalog did not contain any valid products")
        if cache:
            self._write_cache(payload, filename)
        with self._lock:
            self._products = result.products
            self._validation_report = result.report
            self._last_attempt_at = now
            self._last_success_at = datetime.now()
            self._last_error = None
            self._using_cache = False
            self._current_source = filename
        return self.get_status()

    def load_cache(self) -> DataSyncStatus:
        cache_file = self._cache_file()
        result = load_catalog(cache_file)
        if not result.products:
            raise RuntimeError("Cached catalog did not contain any valid products")
        with self._lock:
            self._products = result.products
            self._validation_report = result.report
            self._last_attempt_at = datetime.now()
            self._last_success_at = datetime.now()
            self._last_error = None
            self._using_cache = True
            self._current_source = str(cache_file)
        return self.get_status()

    async def refresh_async(self) -> DataSyncStatus:
        return await asyncio.to_thread(self.refresh)

    async def run_auto_refresh(self, interval_minutes: int = 24 * 60) -> None:
        while True:
            await asyncio.sleep(interval_minutes * 60)
            await self.refresh_async()

    async def run_daily_refresh(self, hour: int = 8, minute: int = 0) -> None:
        while True:
            await asyncio.sleep(self._seconds_until(hour, minute))
            await self.refresh_async()

    def _initial_paths(self) -> list[Path]:
        paths: list[Path] = []
        if self.local_catalog_path:
            paths.append(self.local_catalog_path)
        elif DEFAULT_LOCAL_CATALOG.exists():
            paths.append(DEFAULT_LOCAL_CATALOG)
        paths.append(self.fallback_catalog_path)
        return paths

    def _download_latest(self) -> bytes:
        request = Request(self.source_url, headers={"User-Agent": "DreamADozenDataSync/1.0"})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                content_type = response.headers.get("Content-Type", "")
                payload = response.read()
        except URLError as error:
            raise RuntimeError(str(error.reason)) from error
        if not payload:
            raise RuntimeError("Zoho returned an empty file")
        if "html" in content_type.lower():
            raise RuntimeError("Zoho returned an HTML page instead of spreadsheet data")
        return payload

    def _write_cache(self, payload: bytes, filename: str) -> None:
        cache_file = self._cache_file(filename)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        temp_path = cache_file.with_suffix(cache_file.suffix + ".tmp")
        temp_path.write_bytes(payload)
        temp_path.replace(cache_file)

    def _cache_file(self, filename: str | None = None) -> Path:
        if self.cache_path.suffix:
            return self.cache_path
        suffix = Path(filename or "catalog.xlsx").suffix or ".xlsx"
        return self.cache_path.with_suffix(suffix)

    def _load_cache_after_failure(self, message: str, attempted_at: datetime) -> None:
        with self._lock:
            current_products = list(self._products)
        cache_file = self._cache_file()
        if cache_file.exists():
            try:
                result = load_catalog(cache_file)
            except Exception as cache_error:
                message = f"{message}; cached catalog could not be loaded: {cache_error}"
            else:
                current_products = result.products
                with self._lock:
                    self._validation_report = result.report
                    self._current_source = str(cache_file)
        with self._lock:
            self._products = current_products
            self._last_attempt_at = attempted_at
            self._last_error = message
            self._using_cache = bool(current_products)

    def _seconds_until(self, hour: int, minute: int) -> float:
        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return (target - now).total_seconds()


data_provider = ProductDataProvider()
