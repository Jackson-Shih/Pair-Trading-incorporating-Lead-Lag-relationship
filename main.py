#region imports
from AlgorithmImports import *
from Pair import *
from SymbolData import *
from TradingPair import *

from itertools import combinations
import statsmodels.tsa.stattools as ts
import time
import datetime as dt
import pytz
#endregion

class PairsTrading(QCAlgorithm):     
    initial_capital = 1000000

    pairs = [["AAPL","GOOGL"],["KMB","PG"],["CSX","ITW"],["AEE","CMS"],["ELV","UNH"],["IBM","LIN"],["AME","CSX"],["AWK","XEL"],["MDLZ","MSFT"],["INTU","SBUX"],["CL","KMB"],["ABBV","BAX"],["PNC","USB"],["HSY","MDLZ"],["AWK","NI"],["ITW","NSC"],["CL","PG"],["DUK","LNT"],["ABBV","BIIB"],["CMS","XEL"],["CRL","MDT"],["CPT","MAA"],["ESS","UDR"],["ETR","PNW"],["AWK","CMS"]]
    pair_num = 5  # number of pairs to be traded
    pairs = pairs[:pair_num]
    symbols = sorted(list(set([item for sublist in pairs for item in sublist])))  # put pairs into a list of symbols without repeating itself
    num_bar = 390*5  # 390 is 390 min in one trading day, 5 is trading days
    interval = 2     # every 2 min to review whether trade or not
    leverage = 1
    z_cutOff = 3             # the z-score required to get into the trade (in absolute value)
    z_close = 0         # the z-score required to close the pairs (in absolute value)

    def Initialize(self):
        self.SetStartDate(2020, 4, 16)
        self.SetEndDate(2020, 4, 30)
        self.SetCash(self.initial_capital)
        self.SetBenchmark("VOO")
        self.symbol_data = {}    # a dictionary containing symbol data in the format of SymbolData (a class object)
        self.pair_list = []
        self.selected_pair = []
        self.trading_pairs = {}
        self.regenerate_time = datetime.min

        for ticker in self.symbols: # ['A','B','C',...,'Z']
            security = self.AddEquity(ticker, Resolution.Minute)
            symbol = security.Symbol
            self.symbol_data[symbol] = SymbolData(self, symbol, self.num_bar, self.interval)
            
        for pair in self.pairs:
            # e.g. pairs = [['A','B'],['C','D]]
            # symbol_data.values() -> ['A''s SymbolData object, ..., 'D''s SymbolData object]
            # use symbol index to get the corresponding SymbolData object of each ticker in every pair
            x = list(self.symbol_data.values())[self.symbols.index(pair[0])]
            y = list(self.symbol_data.values())[self.symbols.index(pair[1])]
            if x.IsReady and y.IsReady:
                self.pair_list.append(Pairs(x, y))

    def OnData(self, data):
        
        orderProperties = InteractiveBrokersOrderProperties()

        for symbol, symbolData in self.symbol_data.items():
            if data.Bars.ContainsKey(symbol):
                symbolData.Update(data.Bars[symbol])

        # closing existing position
        for pair, trading_pair in self.trading_pairs.copy().items():

            z_score = pair.get_z_score()

            price_x = pair.x.Prices[0].Close
            price_y = pair.y.Prices[0].Close

            slope = pair.get_slope()
            
            # close: when the z-score crosses 0
            if slope*trading_pair.ticket_x.Quantity > 0 and trading_pair.ticket_y.Quantity < 0 and z_score <= self.z_close:   
            
                qty_x = -trading_pair.ticket_x.Quantity
                qty_y = -trading_pair.ticket_y.Quantity

                ticket_x = self.LimitOrder(pair.x.Symbol, qty_x, price_x, orderProperties = orderProperties)
                ticket_y = self.LimitOrder(pair.y.Symbol, qty_y, price_y, orderProperties = orderProperties)

                self.Debug(f'Order {qty_x} shares of {pair.x.Symbol.Value} @ {pair.x.Prices[0].Close} and  {qty_y} shares of {pair.y.Symbol.Value} @ {pair.y.Prices[0].Close}, z = {z_score} to close')
                    
                self.trading_pairs.pop(pair)

                index = self.pairs.index([pair.x.Symbol.Value,pair.y.Symbol.Value])
                self.second_trade[index] = 0

                self.Debug(f'Close {pair.Name}, {z_score}')
            
            elif slope*trading_pair.ticket_x.Quantity < 0 and trading_pair.ticket_y.Quantity > 0 and z_score >= -self.z_close: 

                qty_x = -trading_pair.ticket_x.Quantity
                qty_y = -trading_pair.ticket_y.Quantity

                
                ticket_x = self.LimitOrder(pair.x.Symbol, qty_x, price_x, orderProperties = orderProperties)
                ticket_y = self.LimitOrder(pair.y.Symbol, qty_y, price_y, orderProperties = orderProperties)

                self.Debug(f'Order {qty_x} shares of {pair.x.Symbol.Value} @ {pair.x.Prices[0].Close} and  {qty_y} shares of {pair.y.Symbol.Value} @ {pair.y.Prices[0].Close}, z = {z_score} to close')
                
                self.trading_pairs.pop(pair)
                index = self.pairs.index([pair.x.Symbol.Value,pair.y.Symbol.Value])
                self.second_trade[index] = 0

                self.second_trade[self.pairs.index([pair.x.Symbol.Value,pair.y.Symbol.Value])] = 0

                self.Debug(f'Close {pair.Name}, {z_score}')

        for pair in self.pair_list:
            # get current Price
            price_x = pair.x.Prices[0].Close
            price_y = pair.y.Prices[0].Close

            z_score = pair.get_z_score()
                
            std_x = pair.x.std.Current.Value
            std_y = pair.y.std.Current.Value
            index = self.pairs.index([pair.x.Symbol.Value,pair.y.Symbol.Value])
            slope = pair.get_slope() #slope of moving regression, using for computing weights

            if pair not in self.trading_pairs and std_x != 0 and std_y != 0:  # sometimes (mostly in the beginning, there is no data for std)
                if z_score >= self.z_cutOff:
                    #Calculate order quantity
                    qty_x = self.Portfolio.TotalPortfolioValue*(self.leverage/self.pair_num) * slope / (1 + abs(slope))/price_x 
                    qty_y = self.Portfolio.TotalPortfolioValue*(self.leverage/self.pair_num) * 1 / (1 + abs(slope))/price_y 
                    
                    #the signal-strength-multiplier function
                    qty_x = (2*(abs(z_score)-2)/abs(z_score))*qty_x
                    qty_y = (2*(abs(z_score)-2)/abs(z_score))*qty_y
                    
                    qty_x = abs(qty_x)* slope/abs(slope)
                    qty_y = -abs(qty_y)

                    ticket_x = self.LimitOrder(pair.x.Symbol, qty_x, price_x, orderProperties = orderProperties)
                    ticket_y = self.LimitOrder(pair.y.Symbol, qty_y, price_y, orderProperties = orderProperties)
                    self.trading_pairs[pair] = TradingPair(ticket_x, ticket_y, z_score)

                    self.Debug(f'Slope = {slope}, add {qty_x} shares of {pair.x.Symbol.Value} @ {pair.x.Prices[0].Close} and {qty_y} shares of {pair.y.Symbol.Value} @ {pair.y.Prices[0].Close}, z = {z_score}')
                    
                elif z_score <= -self.z_cutOff:
                    qty_x = self.Portfolio.TotalPortfolioValue*(self.leverage/self.pair_num) * slope / (1 + abs(slope))/price_x
                    qty_y = self.Portfolio.TotalPortfolioValue*(self.leverage/self.pair_num) * 1 / (1 + abs(slope))/price_y
                    
                    #the signal-strength-multiplier function
                    qty_x = (2*(abs(z_score)-2)/abs(z_score))*qty_x
                    qty_y = (2*(abs(z_score)-2)/abs(z_score))*qty_y
                        
                    qty_x = -abs(qty_x)* slope/abs(slope)
                    qty_y = abs(qty_y)
                        
                    ticket_x = self.LimitOrder(pair.x.Symbol, qty_x, price_x)
                    ticket_y = self.LimitOrder(pair.y.Symbol, qty_y, price_y)
                    self.trading_pairs[pair] = TradingPair(ticket_x, ticket_y, z_score)

                    self.Debug(f'Slope = {slope}, add {qty_x} shares of {pair.x.Symbol.Value} @ {pair.x.Prices[0].Close} and {qty_y} shares of {pair.y.Symbol.Value} @ {pair.y.Prices[0].Close}, z = {z_score}')
    

