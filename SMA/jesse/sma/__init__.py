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


class sma(Strategy):
    def __init__(self):
        super().__init__()
        
        self.vars["risk"] = 10
        self.vars["max_pyramiding_levels"] = 5
        self.vars["sma_period"] = 20
        self.vars["current_pyramiding_level"] = 0
        self.vars["time"] = time.time()
     
    def hyperparameters(self):
        return [ 
            {'name': 'target_perc', 'title': 'Target Loss to Average Down (%)', 'type': float, 'max': 0.0, 'default': -0.1},
            {'name': 'take_profit', 'title': 'Target Take Profit', 'type': float, 'min': 0.0, 'default': 0.1},
            {'name': 'target_qty', 'title': '% Of Current Holdings to Buy', 'type': float, 'min': 0.0, 'default': 0.5},
        ]
    @property
    def sma(self):
        return ta.sma(self.candles, self.vars["sma_period"], sequential=True)

    def should_long(self) -> bool:
        return utils.crossed(self.candles[:, 2], self.sma, 'above')
        # crossover(close, ma)

    def should_short(self) -> bool:
        return False

    def should_cancel(self) -> bool:
        return True

    def pnl_value(self):
        return (self.price - self.average_entry_price) / self.average_entry_price

    def take_profit_level(self):
        return (self.price * (1 + self.hp["take_profit"]))

    def write_to_file(self, row):
        path = "log"
        filename = str(self.vars["time"]) + "_" + str(self.symbol) +"_"+ str(self.timeframe)+ ".csv" 
        with open(os.path.join(path,filename), 'a', encoding='UTF8',newline='') as f:
            writer =  csv.writer(f)
            writer.writerow(row)
    
    def go_long(self):
        qty = utils.risk_to_qty(self.capital, self.vars["risk"], self.price, self.fee_rate)
        self.buy = qty,self.price 
        
        self.take_profit = qty, self.take_profit_level()
        self.vars["current_pyramiding_level"] += 1
       
        row = [self.time, str(self.symbol), self.timeframe,"entry long", self.buy,  self.take_profit, self.vars["current_pyramiding_level"], self.metrics]
        print(row, "\n\n")
        self.write_to_file(row)

    def go_short(self):
        pass
    
    # def increase_position(self):

    def update_position(self):
        if self.vars["current_pyramiding_level"] <= self.vars["max_pyramiding_levels"]:
            if (self.pnl_value() <= self.hp["target_perc"]):
                qty = floor(self.position.qty * self.hp["target_qty"])
                self.buy = qty, self.price
                self.vars["current_pyramiding_level"] += 1
                row = [self.time, str(self.symbol), self.timeframe,"additional long", self.buy,  self.take_profit, self.vars["current_pyramiding_level"], self.metrics]
                print(row, "\n\n")
                self.write_to_file(row)
        else: 
            self.take_profit = self.position.qty, self.take_profit_level()
            self.liquidate() #closes the position with a market order
            row = [self.time, str(self.symbol), self.timeframe,"exit", self.buy,  self.take_profit, self.vars["current_pyramiding_level"], self.metrics]
            print(row, "\n\n")
            self.vars["current_pyramiding_level"] = 0
            self.write_to_file(row)
