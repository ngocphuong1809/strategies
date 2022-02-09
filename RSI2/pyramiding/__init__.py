from ast import Pass
from jesse.strategies import Strategy, cached
import jesse.indicators as ta
from jesse import utils


class pyramiding(Strategy):
    def __init__(self):
        super().__init__()

        self.current_pyramiding_levels = 0
        self.last_opened_price = 0
        self.last_was_profitable = False

    def before(self):
        self.vars["maximum_pyramiding_levels"] = 5
        self.vars["system_type"] = "S1"    
        self.vars["fast_sma_period"] = 5
        self.vars["slow_sma_period"] = 200
        self.vars["rsi_period"] = 2
        self.vars["rsi_ob_threshold"] = 90
        self.vars["rsi_os_threshold"] = 10
        
    def hyperparameters(self):
        return [
                {'name':'stop_loss', 'type': float, 'min': .5, 'max': .99, 'default': .9},
                {'name':'take_profit', 'type': float, 'min': 1.1, 'max': 1.2, 'default': 1.1},
        ]

    @property
    def fast_sma(self):
        return ta.sma(self.candles, self.vars["fast_sma_period"])

    @property
    def slow_sma(self):
        return ta.sma(self.candles, self.vars["slow_sma_period"])

    @property
    def rsi(self):
        return ta.rsi(self.candles, self.vars["rsi_period"])

    def entry_signal(self):
        signal = None
        # Enter long if current price is above sma(200) and RSI(2) is below oversold threshold
        if self.price > self.slow_sma and self.rsi <= self.vars["rsi_os_threshold"]:
            signal = "entry_long"
        # Enter short if current price is below sma(200) and RSI(2) is above oversold threshold
        elif self.price < self.slow_sma and self.rsi >= self.vars["rsi_ob_threshold"]:
            signal = "entry_short"
        
        return signal

    def exit_signal(self):
        signal = None
        # Exit long position if price is above sma(5)
        if self.is_long and self.price > self.fast_sma:
            signal = "exit_long"
    
        # Exit short position if price is below sma(5)
        if self.is_short and self.price < self.fast_sma:
            signal = "exit_short"
        return signal

    def should_long(self) -> bool:
        return self.entry_signal() == "entry_long"

    def should_short(self) -> bool:
        return self.entry_signal() == "entry_short"

    def should_cancel(self) -> bool:
        pass
    
    def go_long(self):
        risk_perc = 3
        qty = utils.risk_to_qty(self.capital, risk_perc, self.price, self.fee_rate)
        self.buy = qty, self.price
        self.stop_loss = qty, (self.price * self.hp['stop_loss'])        # Willing to lose 10%
        self.take_profit = qty, (self.price * self.hp['take_profit'])     # Take profits at 10%   
        self.current_pyramiding_levels += 1 # Track the pyramiding level
        self.last_opened_price = self.price # Store this value to determine when to add next pyramiding 

    def go_short(self):
        risk_perc = 3
        qty = utils.risk_to_qty(self.capital, risk_perc, self.price, self.fee_rate)
        # self.sell = qty, self.price
        self.sell = [
            (qty/2, self.price*1.1),
            (qty/2, self.price*1.2)
        ]
        self.current_pyramiding_levels += 1 # Track the pyramiding level
        self.last_opened_price = self.price # Store this value to determine when to add next pyramiding

    def update_position(self):
        # Handle for pyramiding rules
        if self.current_pyramiding_levels < self.vars["maximum_pyramiding_levels"]:
            # if self.is_long and self.price > self.last_opened_price + (self.vars["pyramiding_threshold"] * self.atr):
            if self.is_long and self.price > self.last_opened_price *1.1 and self.price < self.last_opened_price *1.2:
                risk_perc = 3
                qty = utils.risk_to_qty(self.capital, risk_perc, self.price, self.fee_rate)
                self.buy = qty, self.price
            
            if self.is_short and self.price < self.last_opened_price * 0.9 and self.price > self.last_opened_price * 0.8  :
                risk_perc = 3
                qty = utils.risk_to_qty(self.capital, risk_perc, self.price, self.fee_rate)
                self.sell = qty, self.price 
        
        if self.is_long and (self.entry_signal() == "entry_short" or self.exit_signal() == "exit_long") \
                or self.is_short and (self.entry_signal() == "entry_long" or self.exit_signal() == "exit_short"):
            self.liquidate()
            self.current_pyramiding_levels = 0

    def on_increased_position(self, order):
        if self.is_long:
            self.stop_loss = abs(self.position.qty), self.price * self.hp['stop_loss']  
        if self.is_short:
            self.stop_loss = abs(self.position.qty), self.price * self.hp['take_profit']
        self.current_pyramiding_levels += 1
        self.last_opened_price = self.price
       
    def on_stop_loss(self, order):
        # Reset tracked pyramiding levels
        self.current_pyramiding_levels = 0 

    def on_take_profit(self, order):
        self.last_was_profitable = True

        # Reset tracked pyramiding levels
        self.current_pyramiding_levels = 0 
    
    def filters(self):
        return [
            self.S1_filter
        ]

    def S1_filter(self):
        if self.vars["system_type"] == "S1" and self.last_was_profitable:
            # self.log(f"prev was profitable, do not enter trade")
            self.last_was_profitable = False
            return False
        return True
    
    
