import hashlib
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter
from tokenizers import Tokenizer

from config import settings

# The model's actual tokenizer (loaded from the HuggingFace cache baked into the
# image at build time; runtime is offline). Used to measure chunk sizes in real
# tokens rather than a character/word estimate.
_tokenizer = Tokenizer.from_pretrained(settings.EMBEDDING_MODEL)
# This tokenizer ships with padding/truncation enabled (it pads every input to a
# fixed length for inference). We use it only to COUNT tokens, so disable both —
# otherwise every encode() returns the padded length and counts are meaningless.
_tokenizer.no_padding()
_tokenizer.no_truncation()


def token_length(text: str) -> int:
    """Exact content-token count for `text` (excludes the [CLS]/[SEP] special
    tokens the model adds at embed time)."""
    return len(_tokenizer.encode(text, add_special_tokens=False).ids)


# One splitter, configured once. chunk_size/overlap are measured in tokens via
# length_function. Separators are tried in order: paragraph -> line -> sentence
# -> word -> character, so we break on the largest natural boundary that fits.
_splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.CHUNK_TARGET_TOKENS,
    chunk_overlap=settings.CHUNK_OVERLAP_TOKENS,
    length_function=token_length,
    separators=["\n\n", "\n", ". ", " ", ""],
)


@dataclass(frozen=True)
class ChunkData:
    """One chunk of content plus where it came from. No embedding yet —
    that is added at ingest time (Chunk 5)."""

    course_id: str
    module_id: str
    lesson_id: str
    chunk_index: int
    content: str
    content_hash: str


def chunk_course(course: dict) -> list[ChunkData]:
    """Turn a structured course into an ordered list of chunks.

    Expected shape:
        {
          "course_id": "...",
          "modules": [
            {"module_id": "...", "lessons": [
              {"lesson_id": "...", "content": "..."}
            ]}
          ]
        }

    Each lesson is split independently, so editing one lesson never changes
    another lesson's chunks (boundary-shift isolation). chunk_index resets per
    lesson for the same reason.
    """
    chunks: list[ChunkData] = []
    course_id = course["course_id"]

    for module in course.get("modules", []):
        module_id = module["module_id"]
        for lesson in module.get("lessons", []):
            lesson_id = lesson["lesson_id"]
            content = lesson.get("content", "")
            if not content or not content.strip():
                continue

            for index, piece in enumerate(_splitter.split_text(content)):
                text = _normalize(piece)
                if not text:
                    continue
                chunks.append(
                    ChunkData(
                        course_id=course_id,
                        module_id=module_id,
                        lesson_id=lesson_id,
                        chunk_index=index,
                        content=text,
                        content_hash=_hash(text),
                    )
                )
    return chunks


def _normalize(text: str) -> str:
    """Collapse all whitespace runs to single spaces. Makes hashing robust to
    cosmetic reformatting so we don't re-embed on whitespace-only edits."""
    return " ".join(text.split())


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
