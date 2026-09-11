# 킥앤런 디지털 작전판 — Streamlit MVP v3

GitHub + Streamlit Community Cloud 배포용 프로젝트입니다.

## v3 핵심 변경

- 공격팀을 선택하면 **현재 키커 1명만 HOME 앞에 배치**됩니다.
- 나머지 공격 선수는 경기장 오른쪽 **공격 대기석**에 표시됩니다.
- `다음 키커` 버튼을 누르면 다음 번호 선수가 HOME 앞으로 자동 이동합니다.
- 안전지대에 **3개의 자리 표시**와 `안전지대 n / 3` 카운터가 보입니다.
- 수비팀은 기존처럼 필드에 기본 배치됩니다.
- A/B 공격팀을 바꾸면 위 구성이 즉시 반대로 재배치됩니다.
- 선수/공 드래그, 팀 인원 조절, 팀별 공유, 교사용 보기 기능은 유지됩니다.

## GitHub에 올릴 파일

저장소 루트에 아래 구조를 그대로 올리세요.

```text
app.py
game_state.py
requirements.txt
README.md
run_local.bat
tests/
```

`.streamlit/config.toml`이 ZIP에 들어 있다면 `.streamlit/` 폴더도 함께 올리면 됩니다.

> v2에서 업데이트하는 경우 **app.py와 game_state.py 둘 다 교체**하세요. v3에서는 대기/필드 상태와 현재 키커 정보를 공유 상태에 저장합니다.

## 배포 주소

- A팀: `https://내앱주소.streamlit.app/?team=A`
- B팀: `https://내앱주소.streamlit.app/?team=B`
- 교사: `https://내앱주소.streamlit.app/?team=T`

## 참고

현재 공유 상태는 Streamlit 서버 메모리에 저장되므로 앱이 재시작되면 초기화됩니다.
