from pathlib import Path
from typing import Callable, Awaitable

ProcessorFn = Callable[[Path], Awaitable[Path]]

class ProcessingPipeline:
    def __init__(self):
        self.processors: dict[str, ProcessorFn] = {}
        self._register_defaults()

    def _register_defaults(self):
        from transfer.processors.tiff import flatten_tiff
        self.processors[".tif"] = flatten_tiff
        self.processors[".tiff"] = flatten_tiff

    async def process(self, file_path: Path) -> Path:
        ext = file_path.suffix.lower()
        processor = self.processors.get(ext)
        if processor:
            return await processor(file_path)
        return file_path
