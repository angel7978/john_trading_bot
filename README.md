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
텔레그램에서 @arbitrage_johnpak_bot 찾아서 start 후 <br />
config 파일 내 telegram_id 부분에 텔레그램 id 넣기 <br />
(안드로이드 세팅 -> 계정 및 백업 -> 계정 관리 -> 텔레그램에서 확인 가능)

<h2>기본 로직 (Long)</h2>
<ul>
<li>시장가 매수, 매도로 거래</li>
<li>지표</li>
<ul>
<li>볼린저밴드 Length 20, Mult 2</li>
<li>RSI Length 14</li>
</ul>
<li>진입 조건</li>
<ul>
<li>볼린저 30분봉 종가기준 하단에 닿으면 다음봉 시가에 시장가매수 (20%)</li>
<ul>
<li>(TBD)볼린저밴드 상하단 차이가 3%이하일 시 진입하지 않음</li>
<li>(TBD)4%이상 급락시 진입하지 않음</li>
<li>직전 BTC 12h/ETH 6h 캔들 기준 low 값이 볼린저밴드 하단 아래일 경우 하락장이라고 판단하여 롱 진입하지 않음</li>
</ul>
</ul>
<li>if 수익</li>
<ul>
<li>close 값이 볼린저밴드 상단의 4/5 이상일 시 전수 시장가 매도</li>
<li>볼린저 상단 가격에 매도 주문을 넣어놓아 볼린저밴드 상단을 뚫는 꼬리 발생시에도 매도가 될 수 있도록 함</li>
</ul>
<li>if 손실</li>
<ul>
<li>조건1 : 볼린저밴드 종가기준으로 하단 아래에서 위로 뚫는 양봉 확인시 5% 추가매수</li>
<li>조건2 : 볼린저밴드 이전캔들이 양봉이고 볼린저밴드 하단 아래 and 이번캔들이 양봉이고 볼린저밴드 하단 위 일시 5% 추가매수</li>
<li>조건3 : RSI 30이하에서 이상으로 뚫으면 다음봉에 5% 추가매수</li>
<ul>
<li>조건이 동시에 만족하면 각각 5%씩 추가매수</li>
<li>단, 매수 가격이 평단가보다 높을경우 추가매수를 하지 않음</li>
</ul>
</ul>
<li>S/L 정책</li>
<ul>
<li>총 매수 금액이 원금의 50%가 넘게 되면 보유수량의 절반 매도 후 'if손실' 조건으로 지속 진행</li>
<li>직전 BTC 12h/ETH 6h 캔들 기준 low 값이 볼린저밴드 하단 아래로 떨어진 경우 Long 포지션 강제 종료</li>
</ul>
<li>바이낸스에서 BTCUSDT, ETHUSDT 두 개 체인 x5로 선물 거래</li>
<ul>
<li>각각 총 보유액의 50%씩 할당하여 사용</li>
<li>ex) 현재 토탈 보유 USDT가 1000USDT일 경우 BTCUSDT에 50%인 500USDT 할당, 최초 진입 시 여기에 20%인 100USDT 진입</li>
</ul>
<li>조건 반대로해서 Short 로직 추가</li>
</ul>
