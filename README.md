# john_trading_bot


<h2>바이낸스 api 발급</h2>
Enable Reading, Enable Spot & Margin Trading, Enable Futures 체크


<h2>config 파일 설정</h2>
config_example.json => config.json 으로 변경 후 내용 채워 넣기


<h2>python 3.7 이상 구동</h2>
> python bb_bot.py config.json


<h2>모듈 설치</h2>
> pip install ccxt <br />
> pip install ta <br />
> pip install matplotlib


<h2>텔레그램 push 받고 싶을 경우</h2>
@arbitrage_johnpak_bot 찾아서 start 후 <br />
config 파일 내 telegram_id 부분에 텔레그램 id 넣기 (안드로이드 세팅 -> 계정 및 백업 -> 계정 관리 -> 텔레그램에서 확인 가능) 


<h2>기본 로직 (롱)</h2>
<ul>
<li>시장가 매수, 매도로 거래</li>
<li>진입 조건</li>
<ul>
<li>볼린저 30분봉 종가기준 하단에 닿으면 다음봉 시가에 시장가매수 (20%)</li>
</ul>
<li>if 수익</li>
<ul>
<li>볼린저 상단의 4/5 지점에서 전수 시장가 매도</li>
</ul>
<li>if 손실</li>
<ul>
<li>조건1 : 볼린저 밴드 종가기준으로 하단 아래에서 위로 뚫는 양봉 확인시 5프로 추가매수</li>
<li>조건2 : 볼린저 밴드 이전캔들이 양봉이고 볼린저벤드 하단 아래 and 이번캔들이 양봉이고 볼린저벤드 하단 위 일시 5프로 추가매수</li>
<li>조건3 : RSI 30이하에서 이상으로 뚫으면 다음봉에 5% 추가매수</li>
<li>조건이 동시에 만족하면 각각 5프로씩 추가매수</li>
<li>물탄비율이 원금의 50%가 넘게 되면 보유수량의 절반 매도 후 'if손실' 조건으로 지속 진행</li>
</ul>
<li>바이낸스에서 BTCUSDT, ETHUSDT 두 개 체인 x5로 선물 거래</li>
<ul>
<li>각각 총 보유액의 50프로씩 할당하여 사용</li>
</ul>

<li>조건 반대로해서 숏 추가</li>
</ul>
