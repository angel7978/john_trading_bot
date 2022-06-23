# john_trading_bot

바이낸스 api 발급
- Enable Reading, Enable Spot & Margin Trading, Enable Futures 체크

config 파일 설정
- config_example.json => config.json 으로 변경 후 내용 채워 넣기

python 3.7 이상 구동
> python main.py config.json

모듈 설치
> pip install ccxt
> pip install ta
> pip install matplotlib

텔레그램 push 받고 싶을 경우
- @arbitrage_johnpak_bot 찾아서 start 후
- config 파일 내 telegram_id 부분에 텔레그램 id 넣기 (안드로이드 세팅 -> 계정 및 백업 -> 계정 관리 -> 텔레그램에서 확인 가능) 
