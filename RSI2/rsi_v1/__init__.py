from jesse.strategies import Strategy, cached
import jesse.indicators as ta
from jesse import utils


class rsi_v1(Strategy):
    def __init__(self):
        super().__init__()

        self.current_pyramiding_levels = 0
        self.last_opened_price = 0
        self.last_was_profitable = False
        self.risk = 3

    def before(self):
        self.vars["maximum_pyramiding_levels"] = 5
        self.vars["system_type"] = "S1"    
        self.vars["fast_sma_period"] = 50
        self.vars["slow_sma_period"] = 200
        self.vars["rsi_period"] = 2
        self.vars["rsi_ob_threshold"] = 90
        self.vars["rsi_os_threshold"] = 10
        self.vars["long_rate_1"] = 1.1
        self.vars["long_rate_2"] = 1.15
        self.vars["short_rate_1"] = 0.9
        self.vars["short_rate_2"] = 0.85



        
    def hyperparameters(self):
        return [
                {'name':'long_stop_loss', 'type': float, 'min': .5, 'max': .99, 'default': .9},
                {'name':'short_stop_loss', 'type': float, 'min': 1.1, 'max': 1.2, 'default': 1.1},
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
        # Exit long position if price is above sma(50)
        if self.is_long and self.price > self.fast_sma:
            signal = "exit_long"
    
        # Exit short position if price is below sma(50)
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
        stop = self.price * self.hp["long_stop_loss"]
        qty = utils.risk_to_qty(self.capital, self.risk, self.price, stop, self.fee_rate)
        self.buy = qty, self.price
        self.stop_loss = qty, stop
        self.current_pyramiding_levels += 1 # Track the pyramiding level
        self.last_opened_price = self.price # Store this value to determine when to add next pyramiding 

    def go_short(self):
        stop = self.price * self.hp["short_stop_loss"]
        qty = utils.risk_to_qty(self.capital, self.risk, self.price, stop, self.fee_rate)
        self.sell = qty, self.price
        self.stop_loss = qty, stop
        self.current_pyramiding_levels += 1 # Track the pyramiding level
        self.last_opened_price = self.price # Store this value to determine when to add next pyramiding

    def update_position(self):
        # Handle for pyramiding rules
        if self.current_pyramiding_levels < self.vars["maximum_pyramiding_levels"]:
            if self.is_long and self.price > self.last_opened_price * self.vars["long_rate_1"] and self.price <= self.last_opened_price * self.vars["long_rate_2"]:
                qty = utils.risk_to_qty(self.capital, self.risk, self.price, self.fee_rate)
                self.buy = qty, self.price
            
            if self.is_short and self.price < self.last_opened_price * self.vars["short_rate_1"] and self.price >= self.last_opened_price * self.vars["short_rate_2"] :
                qty = utils.risk_to_qty(self.capital, self.risk, self.price, self.fee_rate)
                self.sell = qty, self.price 
        
        if self.is_long and (self.entry_signal() == "entry_short" or self.exit_signal() == "exit_long") \
                or self.is_short and (self.entry_signal() == "entry_long" or self.exit_signal() == "exit_short"):
            self.liquidate()
            self.current_pyramiding_levels = 0

    def on_increased_position(self, order):
        if self.is_long:
            self.stop_loss = abs(self.position.qty), self.price * self.hp['long_stop_loss']  
        if self.is_short:
            self.stop_loss = abs(self.position.qty), self.price * self.hp['short_stop_loss']
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
    
    
