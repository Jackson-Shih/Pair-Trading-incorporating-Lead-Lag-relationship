#region imports
from AlgorithmImports import *
#endregion

class SymbolData(object):

    def __init__(self, algorithm, symbol, lookback, interval):
        lookback = int(lookback)
        self.Symbol = symbol
        self.Prices = RollingWindow[TradeBar](lookback // interval)
        self.std = algorithm.STD(symbol, 390*2, Resolution.Minute)  # TO_DO: change it into std of return
        self.Series = None
        self.DataFrame = None
        self._algorithm = algorithm
        self._consolidator = TradeBarConsolidator(timedelta(minutes=interval))
        self._consolidator.DataConsolidated += self.OnDataConsolidated

        history = algorithm.History(symbol, lookback, Resolution.Minute)
        self.history = history
        for bar in history.itertuples():
            trade_bar = TradeBar(bar.Index[1], symbol, bar.open, bar.high, bar.low, bar.close, bar.volume)
            self.Update(trade_bar)
            
    @property
    def IsReady(self):
        return self.Prices.IsReady
    
    def Update(self, trade_bar):
        self._consolidator.Update(trade_bar)
    
    def OnDataConsolidated(self, sender, consolidated):
        self.Prices.Add(consolidated)
        if self.IsReady:
            self.Series = self._algorithm.PandasConverter.GetDataFrame[TradeBar](self.Prices)['close']
            self.DataFrame = self.Series.to_frame()