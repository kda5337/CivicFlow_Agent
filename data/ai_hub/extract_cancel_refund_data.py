"""AI Hub 71844('민간 민원 상담 LLM 사전학습 및 Instruction Tuning 데이터')에서
상담주제 '취소/반품/교환/환불/AS'에 해당하는 상담건의 요약(summary) 데이터만 뽑아 저장한다.

AI Hub가 공개한 "세부 분류 유형 분포" 통계의 "취소/반품/환불/AS" 버킷은
consulting_category 원본값을 몇 개로 묶은 것인데, 정확한 매핑표는 로그인이 필요한
"데이터 설명서"에만 있어 접근할 수 없었다. 대신 분류(classification) 라벨링데이터의
consulting_category에 관련 키워드가 하나라도 포함되면 그 상담건(source, source_id)을
매칭시키고, 요약 라벨링데이터에서 같은 상담건에 속한 데이터만 골라 담는다.
(해지/위약금은 통신·카드사에서 사실상 취소에 해당하는 표현이라 키워드에 포함시켰다.
전체 세션 수(11,033)에 대비한 비율로 역산했을 때, '분실'(도난/분실 신청/해제, 휴대폰
정지/분실/파손)을 AS 관련으로 포함해야 AI Hub가 공개한 1,629건/13.22%에 가장 가까워져
키워드에 추가했다.)

대상: 3개 회사(액티벤처/엘지유플러스/하나카드) x Training/Validation. 분류 데이터로 세션을 매칭한 뒤 요약 데이터만 가져온다.

실행:
    python data/ai_hub/extract_cancel_refund_data.py
"""
import io
import json
import os
import tarfile
import urllib.request
import zipfile
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATASET_KEY = "71844"
KEYWORDS = ("취소", "반품", "교환", "환불", "AS", "해지", "위약금", "분실")
OUTPUT_PATH = Path(__file__).resolve().parent / "cancel_refund_summaries.json"

COMPANIES = ["액티벤처", "엘지유플러스", "하나카드"]
SPLITS = ["Training", "Validation"]

# (회사, split) -> {분류: filekey, 요약: filekey, 질의응답: filekey}
FILE_KEYS = {
    ("액티벤처", "Training"): {"분류": "553217", "요약": "553218", "질의응답": "553219"},
    ("엘지유플러스", "Training"): {"분류": "553220", "요약": "553221", "질의응답": "553222"},
    ("하나카드", "Training"): {"분류": "553223", "요약": "553224", "질의응답": "553225"},
    ("액티벤처", "Validation"): {"분류": "553229", "요약": "553230", "질의응답": "553231"},
    ("엘지유플러스", "Validation"): {"분류": "553232", "요약": "553233", "질의응답": "553234"},
    ("하나카드", "Validation"): {"분류": "553235", "요약": "553236", "질의응답": "553237"},
}


def fetch_zip(api_key: str, file_key: str) -> zipfile.ZipFile:
    url = f"https://api.aihub.or.kr/down/0.6/{DATASET_KEY}.do?fileSn={file_key}"
    request = urllib.request.Request(url, headers={"apikey": api_key})
    with urllib.request.urlopen(request, timeout=300) as response:
        tar_bytes = response.read()
    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
        member = tar.getmembers()[0]
        zip_bytes = tar.extractfile(member).read()
    return zipfile.ZipFile(io.BytesIO(zip_bytes))


def matches(category: str) -> bool:
    return any(keyword in category for keyword in KEYWORDS)


def load_records(archive: zipfile.ZipFile) -> list[dict]:
    return [json.loads(archive.read(name))[0] for name in archive.namelist()]


def session_key(record: dict) -> tuple:
    return record.get("source"), record.get("source_id")


def extract(api_key: str) -> list[dict]:
    summaries: dict[tuple, dict] = {}

    for company in COMPANIES:
        for split in SPLITS:
            keys = FILE_KEYS[(company, split)]

            classify_archive = fetch_zip(api_key, keys["분류"])
            classify_records = load_records(classify_archive)
            matched_keys = {
                session_key(record)
                for record in classify_records
                if matches(record.get("consulting_category", ""))
            }
            print(f"[{company}/{split}] 분류 {len(classify_records)}건 중 세션 {len(matched_keys)}건 매칭")

            summary_archive = fetch_zip(api_key, keys["요약"])
            summary_records = load_records(summary_archive)
            found = 0
            for record in summary_records:
                key = session_key(record)
                if key in matched_keys:
                    session = summaries.setdefault(
                        key,
                        {
                            "source": record.get("source"),
                            "source_id": record.get("source_id"),
                            "consulting_category": record.get("consulting_category"),
                            "consulting_content": record.get("consulting_content"),
                            "instructions": [],
                        },
                    )
                    session["instructions"].extend(record.get("instructions", []))
                    found += 1
            print(f"[{company}/{split}] 요약 {len(summary_records)}건 중 {found}건 매칭")

    return list(summaries.values())


if __name__ == "__main__":
    api_key = os.getenv("AI_HUB_API_KEY")
    if not api_key:
        raise SystemExit("AI_HUB_API_KEY가 .env에 설정되어 있지 않습니다.")

    records = extract(api_key)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"\n총 상담건 {len(records)}건 추출 완료 -> {OUTPUT_PATH}")
