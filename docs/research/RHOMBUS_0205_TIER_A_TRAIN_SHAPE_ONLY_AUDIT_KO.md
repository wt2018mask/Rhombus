# RHOMBUS 0205 — TRAIN 초기 경로 형상 검사 (비실행 연구 진단)

## 목적

4개로 고정된 TRAIN 파일럿의 입력 XYZ가 NEB 이미지 시퀀스 형식으로 일관적인지,
**held-out target·DFT relaxed XYZ·원자별 에너지와 힘·원자 좌표를 전혀 해석하지 않고**
바이트와 형식만 검사한다. 기존의 해시 고정으로 입증할 수 없는 이미지 수 및 동일 원자
순서 여부를 추가로 확인한다. 단일 Li 홉의 물리적 정당성, DFT-NEB 수렴, 모델 학습
데이터 노출 여부, 분할 독립성은 여기서 해결되지 않는다.

## 사용자 제공 원본에 대한 실제 확인

- 원본 ZIP: `68,583,182` bytes / SHA256 `b7a99d89337902e9e1da319f57547170fdb132bf15bf6ffef03a0140e2207d7f`
- 검사용 4개 `*_init.xyz`의 압축 해제 총 크기: **1,050,883 bytes**
- 네 개 모두 이미지 **5개**, 이미지 간 **원자 수와 원소 순서 동일**.
- 원자 수(각 이미지): `89`, `111`, `135`, `143`개. Li 원자 수는 각 `9`, `15`, `39`, `89`개.
- 테스트·검증 분할의 XYZ와 `*_relaxed.xyz`는 열지 않았다.
- 원본의 주석·원자 줄에는 `energies` 및 `forces` 같은 필드가 존재한다. 본 검증기는 **주석을 디코딩하지 않고** 원자 줄의 **첫 번째 원소 기호만** 읽는다. 좌표도 읽지 않는다.

이는 **원자 수가 큰 경로가 실제로 존재함**을 의미한다. 두 모델 비교에서는 같은
edge에 대해 동일한 초기 구조·이미지를 사용해야 하며, 전 이미지 수가 같더라도
각 원자계의 추론 비용이 같다고 추정해선 안 된다. 수치 비용 상한은 이 기록만으로
결정할 수 없으므로 아직 미동결이다.

## 개발 파일

- `rhombus/benchmark/tier_a_train_shape_only.py`: 단일 파일 디스크립터로 ZIP 전체 SHA256 대조 → 동일 파일의 허용된 초기 멤버 4개만 읽음 → 이미지 수·원소 순서·Li 원자 수 집계. 바이트·라인·원자·프레임 상한과 경로·중복·해시 검사를 포함.
- `scripts/benchmark/audit_tier_a_train_shape_0205.py`: 기존 owner ZIP 및 고정된 draft·binding receipt 입력을 받아 신규 JSON만 생성. 출력 덮어쓰기 거부.
- `tests/test_tier_a_train_shape_only_0205.py`: target-like 필드 비해석, 비정상 프레임, 누락, 변조, 경로 주입, 용량 초과 등 합성 음성 검사.

```bash
python -m scripts.benchmark.audit_tier_a_train_shape_0205 \
  --archive /path/to/nebDFT2k.zip \
  --draft /path/to/tier_a_equal_budget_input_pinned_DRAFT_NOT_AUTHORIZED.json \
  --input-binding-receipt /path/to/tier_a_four_init_xyz_byte_receipt.json \
  --output /new/empty/path/tier_a_train_shape_only.json
```

**제한:** 파일 바이트의 해시는 소유자 제공 자료의 바이트 연속성을 뜻하며 출판자 인증을
의미하지 않는다. 위 보고서는 새로운 물리 결론도, 실행 승인도 부여하지 않는다.

- `TIER_A_PROTOCOL_DRAFT_READY`
- `BENCHMARK_NOT_FROZEN`
- `TIER_B_NOT_FROZEN`
- `SCIENTIFIC_NO_GO_ABSTAIN`
