"""chroma_duty_free_faq와 chroma_coupang_faq 두 컬렉션을 chroma_merged_faq 하나로 합친다.

두 컬렉션 모두 이미 계산되어 있는 임베딩을 그대로 복사하므로 재임베딩하지 않는다.
metadata.faq_id는 각자 다른 Supabase 테이블(duty_free_faq / coupang_faq) 기준이라 값이
겹칠 수 있어서, 합칠 때 metadata.source_table을 추가해 어느 테이블에서 답변을 찾아야
하는지 구분한다.

원본 컬렉션은 각각 복사가 끝난 직후, target에 같은 건수가 실제로 들어갔는지 확인한
뒤에만 삭제한다(하나가 실패해도 다른 하나까지 잘못 지우지 않도록).

실행:
    cd backend
    python -m app.rag.merge_chroma_faq
"""
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_BACKEND_DIR = str(Path(__file__).resolve().parents[2])
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.rag.vectorstore import get_vectorstore

MERGED_COLLECTION_NAME = "chroma_merged_faq"

# (원본 컬렉션명, 그 컬렉션의 faq_id가 가리키는 Supabase 테이블명)
SOURCE_COLLECTIONS = [
    ("chroma_duty_free_faq", "duty_free_faq"),
    ("chroma_coupang_faq", "coupang_faq"),
]


def merge() -> int:
    target = get_vectorstore(MERGED_COLLECTION_NAME)
    total = 0

    for collection_name, source_table in SOURCE_COLLECTIONS:
        source = get_vectorstore(collection_name)
        result = source._collection.get(include=["documents", "metadatas", "embeddings"])
        ids = result["ids"]
        if not ids:
            print(f"{collection_name}: 데이터가 없어 건너뜁니다.")
            continue

        metadatas = []
        for metadata in result["metadatas"]:
            merged_metadata = dict(metadata or {})
            merged_metadata["source_table"] = source_table
            metadatas.append(merged_metadata)

        target._collection.add(
            ids=ids,
            embeddings=result["embeddings"],
            documents=result["documents"],
            metadatas=metadatas,
        )
        print(
            f"{collection_name}: {len(ids)}건을 '{MERGED_COLLECTION_NAME}'로 복사했습니다 "
            f"(source_table={source_table})."
        )
        total += len(ids)

        copied = target._collection.get(ids=ids)
        if len(copied["ids"]) != len(ids):
            raise SystemExit(
                f"{collection_name}: 복사 건수가 맞지 않아({len(copied['ids'])}/{len(ids)}) "
                "안전을 위해 원본을 삭제하지 않고 중단합니다."
            )
        source.delete_collection()
        print(f"{collection_name}: 복사 확인 후 원본 컬렉션을 삭제했습니다.")

    print(f"총 {total}건을 '{MERGED_COLLECTION_NAME}'에 합쳤습니다.")
    return total


if __name__ == "__main__":
    merge()
