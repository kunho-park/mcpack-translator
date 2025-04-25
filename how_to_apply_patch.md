# 한글패치 적용 방법

## 1. 리소스팩 번역 적용하기

1. 마인크래프트 언어를 한국어로 설정합니다.

2. 다운로드한 `{resourcepack_name}_RESOURCEPACK.zip` 파일을 마인크래프트 옵션의 리소스팩 탭에서 적용해야 합니다.

3. 마인크래프트를 실행하고 옵션션 > 리소스팩 메뉴로 이동합니다.

4. 리소스팩 폴더 열기를 누르고 그 안에 해당 zip 파일을 넣습니다.

5. 사용 가능한 리소스팩 목록에서 한글패치를 선택하고 '완료' 버튼을 클릭합니다.

6. 게임을 재시작하면 한글패치가 적용됩니다.

## 2. 리소스팩으로 번역이 불가능한 기타 번역 적용하기

1. 모드팩 폴더 내 `config` 및 `kubejs`, 등 여러 폴더를 그대로 모드팩 폴더에 덮어쓰기 합니다.

2. 서버에 적용할 경우 모든 클라이언트에서 동일한 버전의 한글패치를 사용해야 합니다.

## 3. 문제 해결

- 한글패치가 제대로 되지 않은 경우우: 마인크래프트 언어 설정을 한국어로 변경해주세요.

## 4. 추가 정보

- 이 패치는 마인크래프트 1.20+ 버전을 기준으로 제작되었습니다.
- 커스텀 사전을 사용하려면 `translation_dictionary.json` 파일을 수정하세요.

### 이 모드팩은 mcpack-translator로 번역 되었습니다.
- 가이드: https://kunho-park.notion.site/1dc8edfca9988073a109f2b746f1aa8d
- 깃허브: https://github.com/kunho-park/mcpack-translator

### 사용된 옵션
- Provider: {provider}
- Model: {model}
- Temperature: {temperature}
- Worker Number: {worker_num}
- File Split: {file_split}