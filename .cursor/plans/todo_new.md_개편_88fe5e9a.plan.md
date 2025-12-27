---
name: TODO 로드맵 문서 개편
overview: PRD.md를 기준으로 Phase 구조를 통일하고, DESIGN-SPEC.md의 UI/UX 개선 사항을 통합하여 개발자 친화적인 로드맵 문서로 재구성합니다. 기존 문서는 TODO_v1.md로 보존하고, 새 문서는 TODO_v2.md로 작성합니다.
todos:
  - id: rename-to-v1
    content: 기존 TODO_new.md를 TODO_v1.md로 이름 변경
    status: pending
  - id: create-v2
    content: TODO_v2.md 새로 작성 (작성일자 2025-12-25 기입)
    status: pending
  - id: add-tech-decisions
    content: 기술 결정 사항 섹션 추가 (Phoenix, 상태관리 등)
    status: pending
  - id: integrate-prd
    content: PRD.md의 Phase 5-9 내용 통합
    status: pending
  - id: integrate-design
    content: DESIGN-SPEC.md의 UI/UX 백로그 통합
    status: pending
  - id: add-considerations
    content: 각 Phase별 사전 검토 사항/리스크 추가
    status: pending
---

# TODO 로드맵 문서 개편 플랜

## 현재 문제점

1. **Phase 번호 불일치**: PRD, DESIGN-SPEC, TODO_new.md 간 Phase 체계가 다름
2. **누락된 항목**: PRD/DESIGN-SPEC에 있는 향후 계획이 TODO에 미반영
3. **불필요한 항목**: TanStack Query 관련 내용 (도입 안 하기로 결정)
4. **구조적 문제**: 단순 체크리스트 나열로 맥락/의사결정 근거 부족

## 개편 방향

### 1. 문서 구조 재편성

```javascript
TODO_new.md
├── 1. 현재 상태 요약 (MVP v1.0 완료)
├── 2. 기술 결정 사항 (Technology Decisions)
├── 3. 로드맵 개요 (Phase 5-9 타임라인)
├── 4. Phase별 상세 계획
│   ├── Phase 5: 크롤러 확장 & 입력 검증
│   ├── Phase 6: LLMOps & Evaluation (Phoenix)
│   ├── Phase 7: 품질 개선 전략
│   ├── Phase 8: Cloud 인프라 & CI/CD
│   └── Phase 9: 문서화 & 공유
├── 5. UI/UX 개선 백로그
└── 6. 참고 자료 (관련 문서, 실행 환경)
```



### 2. 주요 변경 사항

#### 삭제할 내용

- Phase 4 (TanStack Query) 전체 섹션 → 도입 안 함
- Langfuse/W&B Weave 관련 내용 → Phoenix로 통일
- 완료된 Phase 1-3 상세 내용 → "현재 상태 요약"으로 압축

#### 추가할 내용 (PRD.md에서)

- 범용 크롤러 (trafilatura 기반) - High Priority
- 입력 검증 (URL 유효성 검사) - High Priority
- Phoenix 통합 상세 계획
- Evaluation Pipeline (RAGAS, LLM-as-a-Judge)
- Long context 대응 전략 (Chunk + Parallel Summarization)
- Agentic workflow (Summarize → Reviewer → Final Writer)
- GCP Storage 마이그레이션
- Cloud 인프라 아키텍처 (Vercel + Cloud Run)

#### 추가할 내용 (DESIGN-SPEC.md에서)

- 오디오 Speed Control (1.0x/1.25x/1.5x/2.0x) - High Priority
- Rewind/Forward 10s - Medium Priority
- URL 검증 피드백 UI - High Priority
- 플랫폼 자동 감지 표시
- 접근성 개선 (키보드 네비게이션, ARIA)
- 공유 기능

### 3. 새로운 섹션별 내용

#### 2. 기술 결정 사항 (신규 섹션)

| 결정 사항 | 선택 | 근거 ||-----------|------|------|| LLMOps 도구 | Phoenix | Arize Phoenix - DSPy 기반, 로컬/클라우드 유연성 || 상태 관리 | useState + fetch 유지 | 현재 기능 충분, 불필요한 복잡도 회피 || TTS 모델 | OpenAI gpt-4o-mini-tts | 품질/비용 균형 || 범용 크롤러 | trafilatura | 다양한 웹사이트 지원, 이미 일부 적용됨 |

#### 4. Phase별 상세 계획 구조

각 Phase마다:

- **목표**: 한 줄 요약
- **사전 검토 사항**: 구현 전 결정해야 할 것들
- **구현 항목**: 체크리스트
- **예상 리스크/고려사항**: 주의할 점
- **완료 조건**: Definition of Done

### 4. UI/UX 개선 백로그 (별도 섹션)

DESIGN-SPEC.md의 UI/UX 항목들을 우선순위별로 정리:| 우선순위 | 항목 | 관련 Phase ||----------|------|------------|| High | Speed Control | Phase 7 || High | URL 검증 피드백 | Phase 5 || Medium | Rewind/Forward 10s | Phase 7 || Medium | 플랫폼 자동 감지 | Phase 5 || Low | 키보드 네비게이션 | Phase 9 || Low | 공유 기능 | Phase 9 |

## 구현 순서

1. **TODO_new.md → TODO_v1.md** 이름 변경 (기존 문서 보존)
2. **TODO_v2.md** 신규 생성 (작성일자: 2025-12-25 명시)
3. 새로운 문서 구조로 작성 (아래 구조 참조)
4. PRD.md, DESIGN-SPEC.md 내용 통합