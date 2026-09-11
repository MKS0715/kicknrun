# 킥앤런 디지털 작전판 — Streamlit MVP

5학년 체육 공개수업용 **킥앤런 팀별 공유 작전판** 1차 프로토타입입니다.

## 1차 구현 기능

- A팀 / B팀 비공개 작전실
- A팀·B팀 인원 `- / +` 조절 (1~12명)
- 인원수에 맞춰 번호 선수 아이콘 자동 생성
- 선수 아이콘 자유 드래그 (마우스/터치)
- 공 자유 드래그
- `A팀 공격 / B팀 공격` 표시 전환
- 공 원위치 / 배치 초기화
- 같은 팀 브라우저 간 약 0.8초 간격 상태 공유
- 교사용 보기 전용 화면
- URL 쿼리로 팀 바로 입장 (`?team=A`, `?team=B`, `?team=T`)

> 기본 인원은 A 8명, B 9명으로 두었습니다. 화면에서 즉시 바꿀 수 있습니다.

## 구조

```text
GitHub
  ↓
Streamlit Community Cloud
  ↓
app.py ── Streamlit Components v2 (HTML/CSS/JS 작전판)
  ↓
game_state.py ── thread-safe 공유 메모리
  ├─ A팀 비공개 작전 상태
  └─ B팀 비공개 작전 상태
```

현재 공유 방식은 `st.cache_resource`에 보관된 서버 메모리를 사용합니다. 따라서 **같은 Streamlit 앱 프로세스에 접속한 사용자끼리 공유**되며, 앱 재시작/휴면 해제 시 상태가 초기화될 수 있습니다. 공개수업 MVP에는 간단하고 빠르지만, 이닝별 저장이나 영구 보관이 필요해지면 Supabase로 저장 계층만 교체하는 것이 다음 단계입니다.

## 로컬 실행

Python 3.11+ 권장.

```bash
pip install -r requirements.txt
streamlit run app.py
```

Windows에서는 `run_local.bat`을 더블클릭해도 됩니다.

## Streamlit Community Cloud 배포

1. 이 폴더의 파일을 GitHub 저장소 루트에 업로드합니다.
2. Streamlit Community Cloud에서 새 앱을 생성합니다.
3. Repository를 선택하고 Main file path를 `app.py`로 지정합니다.
4. 배포가 끝나면 아래 주소를 각각 QR로 만들면 됩니다.

```text
https://YOUR-APP.streamlit.app/?team=A
https://YOUR-APP.streamlit.app/?team=B
https://YOUR-APP.streamlit.app/?team=T
```

A/B팀은 각자 다른 private tactics state를 사용하므로, 서로의 작전판 수정 내용이 섞이지 않습니다. 선수 **인원수만 두 작전판에 공통 적용**됩니다.

## 수업 당일 권장 운영

- 수업 시작 전에 교사용 화면에서 `모든 작전판 초기화`
- A팀 태블릿에는 A팀 QR, B팀 태블릿에는 B팀 QR 제공
- 팀별 1대는 주 조작용, 나머지는 의견 공유/확인용으로 시작
- 작전회의 종료 후 실제 게임 진행

## 다음 구현 후보

1. 손가락으로 **이동/패스 화살표 그리기**
2. `1이닝 작전 저장 → 수정 작전 저장 → 비교`
3. 팀별 `우리 작전 한 줄` 선택형 문구
4. 교사용 A/B팀 동시 미리보기
5. Supabase Realtime/DB 연결로 서버 재시작에도 보존
6. 수업용 QR 자동 생성 화면

## 테스트

상태 관리 로직은 Streamlit 없이 테스트할 수 있습니다.

```bash
python -m unittest discover -s tests -v
```
