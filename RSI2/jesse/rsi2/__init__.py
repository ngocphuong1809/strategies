from math import floor
from re import T
from sqlite3 import Timestamp
from jesse.strategies import Strategy, cached
import jesse.indicators as ta
from jesse import utils
import csv
import os
from datetime import datetime
import time
import pandas as pd



class rsi2(Strategy):
    def __init__(self):
        super().__init__()

        self.vars["risk"] = 3
        self.vars["max_pyramiding_levels"] = 5
        self.vars["current_pyramiding_level"] = 0
        self.vars["time"] = time.time()
        self.vars["fast_sma_period"] = 50
        self.vars["slow_sma_period"] = 200
        self.vars["rsi_period"] = 2
        self.vars["rsi_ob_threshold"] = 90
        self.vars["rsi_os_threshold"] = 10


    def hyperparameters(self):
        return [
        #         {'name':'stop_loss', 'type': float, 'min': .5, 'max': .99, 'default': .9},
        #         {'name':'take_profit', 'type': float, 'min': 1.1, 'max': 1.2, 'default': 1.1},
                {'name': 'target_qty', 'title': '% Of Current Holdings to Buy', 'type': float, 'min': 0.0, 'default': 0.5},
                {'name': 'target_perc', 'title': 'Target Loss to Average Down (%)', 'type': float, 'max': 0.0, 'default': -0.1},
                
                {'name': 'short_take_profit', 'title': 'Short Target Take Profit', 'type': float, 'min': 0.0, 'default': 0.1},
                {'name': 'long_take_profit', 'title': 'Long Target Take Profit', 'type': float, 'min': 0.0, 'default': 0.1},
        
                {'name': 'short_stop_loss', 'title': 'Short Stoploss', 'type': float, 'min': 0.0, 'default': 0.1},
                {'name': 'long_stop_loss', 'title': 'Long Stoploss', 'type': float, 'min': 0.0, 'default': 0.1},

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
    def pnl_value(self):
        return (self.price - self.average_entry_price) / self.average_entry_price

    def long_take_profit_level(self):
        return (self.price * (1 + self.hp["long_take_profit"]))

    def long_stoploss_level(self):
        return (self.price * (1 - self.hp["long_stop_loss"]))

    def short_take_profit_level(self):
        return (self.price * (1 - self.hp["short_take_profit"]))

    def short_stoploss_level(self):
        return (self.price * (1 + self.hp["short_stop_loss"]))

    def write_to_file(self, row):
        path = "log_rsi2"
        filename =  "rsi2_"+ str(self.vars["time"]) + "_" + str(self.symbol) +"_"+ str(self.timeframe)+ ".csv" 
        with open(os.path.join(path,filename), 'a', encoding='UTF8',newline='') as f:
            writer =  csv.writer(f)
            writer.writerow(row)

    def go_long(self):
        qty = utils.risk_to_qty(self.capital, self.vars["risk"], self.price, self.long_stoploss_level(), self.fee_rate)
        self.buy = qty, self.price
        self.stop_loss = qty, self.long_stoploss_level()
        self.take_profit = qty, self.long_take_profit_level()
        self.vars["current_pyramiding_level"] += 1
        row = [self.time, str(self.symbol), self.timeframe,"Entry Long", self.buy, self.vars["current_pyramiding_level"], self.metrics]
        print(row, "\n\n")
        self.write_to_file(row)

    def go_short(self):
        qty = utils.risk_to_qty(self.capital, self.vars["risk"], self.price, self.short_stoploss_level(), self.fee_rate)
        self.sell = qty, self.price 
        self.stop_loss = qty, self.short_stoploss_level()
        self.take_profit =  qty, self.short_take_profit_level()
        self.vars["current_pyramiding_level"] += 1
        row = [self.time, str(self.symbol), self.timeframe,"Entry Short", self.sell, self.vars["current_pyramiding_level"], self.metrics]
        print(row, "\n\n")
        self.write_to_file(row)

    def update_position(self):

        if self.vars["current_pyramiding_level"] <= self.vars["max_pyramiding_levels"]:
            if (self.pnl_value() <= self.hp["target_perc"]):
                if self.is_long:
                    qty = floor(self.position.qty * self.hp["target_qty"])
                    self.buy = qty, self.price
                    self.vars["current_pyramiding_level"] += 1
                    row = [self.time, str(self.symbol), self.timeframe,"Additional long", self.buy, self.vars["current_pyramiding_level"], self.metrics]
                    print(row, "\n\n")
                    self.write_to_file(row)

                if self.is_short:
                    qty = floor(self.position.qty * self.hp["target_qty"])
                    self.sell = qty, self.price 
                    self.vars["current_pyramiding_level"] += 1
                    row = [self.time, str(self.symbol), self.timeframe,"Additional short", self.sell, self.vars["current_pyramiding_level"], self.metrics]
                    print(row, "\n\n")
                    self.write_to_file(row)
        else:
            if  self.exit_signal() == "exit_long":
                self.liquidate()
                row = [self.time, str(self.symbol), self.timeframe,"Exit Long", "" ,   self.vars["current_pyramiding_level"], self.metrics]
                print(row, "\n\n")
                self.write_to_file(row)
                self.vars["current_pyramiding_level"] = 0
            
            if self.exit_signal() == "exit_short":
                self.liquidate()
                row = [self.time, str(self.symbol), self.timeframe,"Exit Short", "" , self.vars["current_pyramiding_level"], self.metrics]
                print(row, "\n\n")
                self.write_to_file(row)
                self.vars["current_pyramiding_level"] = 0

    # def on_increased_position(self, order):
    #     if self.is_long:
    #         self.stop_loss = abs(self.position.qty), self.price * self.hp['stop_loss']  
    #     if self.is_short:
    #         self.stop_loss = abs(self.position.qty), self.price * self.hp['take_profit']
    #     self.current_pyramiding_levels += 1
    #     self.last_opened_price = self.price
       
    def on_stop_loss(self, order):
        # Reset tracked pyramiding levels
        self.vars["current_pyramiding_level"] = 0

    def on_take_profit(self, order):
        # self.last_was_profitable = True

        # Reset tracked pyramiding levels
        self.vars["current_pyramiding_level"] = 0
    
    # def filters(self):
    #     return [
    #         self.S1_filter
    #     ]

    # def S1_filter(self):
    #     if self.vars["system_type"] == "S1" and self.last_was_profitable:
    #         # self.log(f"prev was profitable, do not enter trade")
    #         self.last_was_profitable = False
    #         return False
    #     return True
    
    
