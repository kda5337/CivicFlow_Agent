"""AI Hub API 연결 테스트: '공공 민원 상담 LLM 사전학습 및 Instruction Tuning 데이터'(71852)의
Validation 질의응답 라벨링 데이터를 내려받아 상위 5건을 출력한다. 완료 후 삭제해도 됨."""
import io
import json
import os
import tarfile
import urllib.error
import urllib.request
import zipfile

from dotenv import load_dotenv

load_dotenv()

DATASET_KEY = "71852"
# Validation/질의응답, 국립아시아문화전당 (라벨링데이터 중 가장 용량이 작은 파일)
FILE_KEY = "553400"
DOWNLOAD_URL = f"https://api.aihub.or.kr/down/0.6/{DATASET_KEY}.do?fileSn={FILE_KEY}"


def fetch_tar(api_key: str) -> bytes:
    request = urllib.request.Request(DOWNLOAD_URL, headers={"apikey": api_key})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        raise SystemExit(f"다운로드 실패 ({error.code}): {error.read().decode('utf-8')}")


def extract_inner_zip(tar_bytes: bytes) -> zipfile.ZipFile:
    """AI Hub 다운로드 응답은 zip 파일 하나를 담은 tar 컨테이너로 온다."""
    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
        member = tar.getmembers()[0]
        zip_bytes = tar.extractfile(member).read()
    return zipfile.ZipFile(io.BytesIO(zip_bytes))


def top_n_records(archive: zipfile.ZipFile, n: int) -> list[dict]:
    records = []
    for name in sorted(archive.namelist())[:n]:
        record = json.loads(archive.read(name))[0]
        records.append(record)
    return records


if __name__ == "__main__":
    api_key = os.getenv("AI_HUB_API_KEY")
    if not api_key:
        raise SystemExit("AI_HUB_API_KEY가 .env에 설정되어 있지 않습니다.")

    tar_bytes = fetch_tar(api_key)
    archive = extract_inner_zip(tar_bytes)
    records = top_n_records(archive, 5)

    print(f"연결 성공. 공공 민원 상담 LLM 데이터 상위 {len(records)}건:")
    for record in records:
        qa = record["instructions"][0]["data"][0]
        print(f"- [{record['source']} / {record['source_id']}] Q: {qa['instruction']} / A: {qa['output']}")
