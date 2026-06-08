# Macaronys Assignment Backend

Discord에서 수행평가와 과제 마감 시간을 관리하고, PDF/TXT/음성/채팅 자료에서 과제 후보를 추출하는 백엔드 프로젝트입니다.

현재 운영 대상은 **Discord만**입니다. 외부 메신저 브리지 코드는 제거되어 Discord 명령어와 알림 흐름만 유지합니다.

## 발표 요약

- 학생과 선생님이 Discord 명령어로 과제와 팀프로젝트를 등록한다.
- 과제 마감까지 남은 시간을 계산해서 Discord 채널로 알림을 보낸다.
- 팀프로젝트 팀원을 모집하고, 프로젝트 종료 뒤 익명 동료 평가를 남긴다.
- PDF, TXT, 음성 녹음, 채팅 내용을 업로드하면 Ollama Gemma가 과제 후보를 추출한다.
- 데이터는 외부 PostgreSQL에 저장한다.
- 기본 AI 실행은 로컬 Ollama입니다. 로컬 worker와 서버 AI 큐는 `AI_WORKER_CONCURRENCY` 값만큼 병렬 처리할 수 있습니다.

## 현재 구현 범위

- FastAPI 백엔드와 자동 API 문서
- 외부 PostgreSQL 전용 연결
- PostgreSQL 스키마: `database/schema.sql`
- Discord slash command 봇
- Discord 명령어 자동완성
- NEIS 급식/시간표 조회
- 과제 CRUD, 알림 예약, 알림 발송
- Discord 반-채널 매핑 기반 알림 전송
- 팀프로젝트 모집, 참여, 완료, 익명 평가
- 관리자 명령어: 역할 이동, 역할 일괄 추가/제거, 일괄 추방, 채널 기록 삭제
- PDF/TXT/채팅 입력 처리
- Ollama Gemma 기반 AI 작업
- 병렬 로컬 AI worker
- Docker Compose 실행
- 테스트 코드

## 구조

```text
Discord Server
  ├─ slash commands
  ├─ class channels
  └─ console channel

Docker / VPS
  ├─ FastAPI API
  ├─ Discord Bot
  └─ external PostgreSQL connection

Local PC
  └─ Ollama + Gemma local AI worker
```

데이터베이스는 로컬 컨테이너로 띄우지 않습니다. `.env`의 외부 PostgreSQL `DATABASE_URL`만 사용합니다.

## 실행 준비

필수 준비물:

- Python 3.11 이상
- Docker Desktop 또는 Docker Engine + Compose v2
- 외부 PostgreSQL 데이터베이스
- Discord Developer Portal에서 만든 봇 토큰
- Ollama
- Gemma 모델 예: `gemma3:4b`

`.env`를 준비합니다.

```bash
cp .env.example .env
```

`.env`에서 최소한 다음 값을 채워야 합니다.

```env
DATABASE_URL=postgresql://...
DISCORD_BOT_TOKEN=...
WORKER_TOKEN=replace-with-random-worker-token
AI_EXECUTION_MODE=local
SERVER_OLLAMA_ENABLED=false
AI_WORKER_CONCURRENCY=2
OLLAMA_MODEL=gemma3:4b
```

`config.json`에는 비밀값을 넣지 않습니다. 봇 토큰, DB URL, worker 토큰 같은 값은 `.env`에만 둡니다.
worker 토큰은 다음처럼 랜덤 값으로 생성합니다.

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 한 번에 실행

macOS/Linux:

```bash
./start.sh
```

기본 실행은 다음을 처리합니다.

- `.venv` 생성
- Python 의존성 설치/업데이트
- Docker 실행 확인
- 외부 DB 설정 확인
- Discord 봇 토큰 확인
- Ollama 확인
- 설치된 Ollama 모델 확인 및 선택
- Docker API 시작
- Docker Discord 봇 시작
- 로컬 AI worker 백그라운드 시작

주요 옵션:

```bash
./start.sh --api-only
./start.sh --docker
./start.sh --local
./start.sh --worker
./start.sh --discord-bot
./start.sh --choose-model
./start.sh --update-python
```

Windows:

```bat
start.bat
```

## Discord 봇 추가법

1. Discord Developer Portal에서 Application을 만든다.
2. Bot 탭에서 토큰을 발급받아 `.env`의 봇 토큰 값에 넣는다.
3. Bot 탭에서 `Server Members Intent`를 켠다.
4. OAuth2 URL Generator에서 scope를 선택한다.
   - `bot`
   - `applications.commands`
5. 권한은 최소 권한 원칙을 사용한다.
   - permission integer: `2435968018`
   - 포함 권한: 역할/채널/메시지 관리, 추방, 임베드, 파일 첨부, 음성 채널 접속/발화/이동, slash command 사용
6. 생성된 URL로 학교 Discord 서버에 봇을 추가한다.
7. 서버에 `console` 채널을 만들고 `config.json`의 `discord.admin.console_channel_id`에 채널 ID를 넣는다.

관리자/선생님용 명령어는 `console` 채널에서만 작동합니다.

## 기본 사용 순서

1. 서버에 봇을 초대한다.
2. `console` 채널을 만들고 채널 ID를 `config.json`에 넣는다.
3. 봇을 실행한다.
4. `console` 채널에서 반 채널을 연결한다.

```text
/반채널연동 반:2-3
```

5. 학생 또는 선생님 계정을 앱 사용자와 연결한다.

```text
/가입 이름:홍길동 생년월일:2009-03-01 반:2-3
```

6. 과제를 등록한다.

```text
/과제추가 제목:역사 수행평가 마감:2026-06-14 23:59 과목:역사 제출:클래스룸
```

7. 과제 목록을 확인한다.

```text
/과제목록
```

## Discord 명령어

일반 명령어:

- `/가입`: Discord 계정을 내부 사용자와 연결
- `/과제목록`: 남은 시간순 과제 조회
- `/급식`: 오늘 급식을 조식/중식/석식 페이지로 조회
- `/시간표`: 현재 학급 채널 기준 오늘 시간표 조회
- `/팀원모집`: 팀프로젝트 모집 글 생성
- `/팀목록`: 모집 중인 팀프로젝트 조회
- `/팀참여`: 팀프로젝트 참여
- `/팀완료`: 프로젝트 완료 처리
- `/팀평가`: 완료된 프로젝트의 팀원을 익명 평가
- `/팀평가요약`: 평가 작성자 없이 요약 조회

선생님/관리자 명령어:

- `/반채널연동`: 현재 채널을 반과 연결
- `/과제추가`: 현재 반 기준 과제 등록
- `/역할이동`: 특정 역할 멤버를 다른 역할로 이동하고 기존 역할 제거
- `/역할일괄추가`: 여러 사용자에게 한 번에 역할 추가
- `/역할일괄제거`: 여러 사용자에게서 한 번에 역할 제거
- `/일괄추방`: 여러 사용자 추방
- `/채널기록삭제`: 최근 메시지 삭제 또는 채널 재생성 방식으로 기록 삭제

관리자 명령어는 다음 조건을 모두 만족해야 작동합니다.

- `console` 채널에서 실행
- 실행자가 Discord 관리자 권한 보유
- 봇 역할이 수정 대상 역할보다 위에 있음
- 위험 명령어는 확인 문구 입력

관리 작업 결과는 `discord_moderation_logs` 테이블에 기록됩니다.

## 자동완성

다음 입력값은 Discord slash command 자동완성을 지원합니다.

- `반`: `school_classes.class_key`
- `과제id`: `assignments.id`
- `프로젝트id`: `team_projects.id`

즉, 긴 UUID를 외우지 않고 명령어 입력 중 후보를 선택할 수 있습니다.

## AI 실행 방식

현재 기본값:

```env
AI_EXECUTION_MODE=local
SERVER_OLLAMA_ENABLED=false
AI_WORKER_CONCURRENCY=2
```

로컬 AI 모드에서는 서버가 AI 작업을 DB에 저장하고, 로컬 worker가 작업을 가져와 로컬 Ollama Gemma로 처리합니다.

```bash
./start.sh --worker
```

서버 AI 모드는 나중에 VPS에서 Ollama를 직접 실행할 때 사용합니다. 이 모드도 `AI_WORKER_CONCURRENCY` 값만큼 병렬 처리합니다.

```env
AI_EXECUTION_MODE=server
SERVER_OLLAMA_ENABLED=true
```

현재 요구사항에서는 서버 Ollama를 꺼 둔 상태입니다.

## 실제로 어디서든 작동하게 하려면 필요한 것

학교나 팀원이 어디서든 쓰려면 로컬 실행이 아니라 운영 배포가 필요합니다.

필수 항목:

- 24시간 켜져 있는 VPS 또는 클라우드 서버
- 고정 접속 주소: 도메인 또는 고정 IP
- HTTPS reverse proxy: Caddy 또는 Nginx
- 외부 PostgreSQL
- Docker Compose 운영 환경
- Discord 봇 토큰과 권한 설정
- `Server Members Intent` 활성화
- 서버 재부팅 후 자동 시작 설정: systemd, Docker restart policy, 또는 배포 플랫폼 설정
- 로그 보관과 장애 알림
- DB 백업 정책
- `.env` 비밀값 관리
- AI를 로컬에서 돌릴 경우 항상 켜져 있는 로컬 worker PC

권장 운영 형태:

```text
VPS
  ├─ Docker Compose: api, discord-bot
  ├─ Caddy/Nginx: HTTPS
  └─ external PostgreSQL

Local AI PC
  ├─ Ollama
  └─ ./start.sh --worker
```

## API 사용

서버 실행 후 문서:

```text
http://localhost:8000/docs
```

헬스 체크:

```bash
curl http://localhost:8000/health
```

정상 예시:

```json
{
  "status": "ok",
  "app": "Macaronys Assignment Backend",
  "ai_execution_mode": "local",
  "ollama_model": "gemma3:4b",
  "database": "ok"
}
```

## 테스트

```bash
.venv/bin/python -m compileall app.py macaronys_backend tests
.venv/bin/python -m pytest
.venv/bin/python -m json.tool config.json
bash -n start.sh
docker compose --profile bot config
```

현재 테스트 범위:

- AI 결과 파서
- 문서 파서
- 시간 계산
- DB URL 정규화
- Discord 설정/자동완성 보조 로직
- 알림 기본 채널
- 팀프로젝트 익명 평가 응답

## 보안 주의

- `.env`는 Git에 올리면 안 됩니다.
- `.env.example`만 안전한 템플릿으로 형상관리합니다.
- Discord 봇 토큰은 한 번 유출되면 즉시 재발급해야 합니다.
- worker API는 `X-Worker-Token`이 설정되어 있어야만 사용할 수 있습니다.
- 관리자 명령어는 `console` 채널에서만 실행되게 유지해야 합니다.
- 채널 전체 삭제와 일괄 추방은 실제 서버에서 테스트 서버로 먼저 검증한 뒤 사용해야 합니다.
- 봇 역할 위치가 낮으면 역할 수정 명령은 실패합니다.
- 봇 초대 권한은 전체 관리자 권한 대신 `config.json`의 최소 권한 정수를 사용합니다.

## 평가 기준 대응

UI/UX:

- 학생 명령어는 `/가입`, `/과제목록`, `/급식`, `/시간표`처럼 자주 쓰는 흐름만 노출합니다.
- 긴 정보는 Discord embed와 페이지 버튼으로 보여줍니다.
- 위험한 관리자 작업은 console 채널과 확인 문구를 요구해 실수를 줄입니다.

소프트웨어 아키텍처:

- API 라우터는 `macaronys_backend/routers`, 비즈니스 로직은 `services`, DTO는 `schemas`, DB 정의는 `models`와 `database/schema.sql`에 둡니다.
- 실행, 보안, 테스트, 운영 배포 절차를 README에 유지합니다.
- `.env.example`, 문서, 테스트, 소스 코드는 형상관리하고 `.env`, 캐시, 런타임 데이터는 제외합니다.

커밋 메시지:

- 형식은 `type(scope): summary`를 사용합니다.
- 예: `feat(discord): add meal and timetable commands`
- 예: `security(worker): require worker token for job APIs`
- 자세한 보안 정책은 `SECURITY.md`, 기여/커밋 규칙은 `CONTRIBUTING.md`에 정리되어 있습니다.

## 다음 개발 후보

- Discord 알림 스케줄러 자동 실행 프로세스
- 웹 프론트엔드
- 파일 업로드 화면
- 과제 후보 검토 화면
- 팀프로젝트 평가 결과 대시보드
- Alembic 마이그레이션 도입
- 운영 로그/모니터링 대시보드
