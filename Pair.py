#region imports
import numpy as np
import pandas as pd
from AlgorithmImports import *
import statsmodels.formula.api as sm
from statsmodels.tsa.stattools import coint, adfuller
from sklearn.linear_model import LinearRegression
import math

#endregion

class Pairs(object):

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.Name = f'{x.Symbol.Value}:{y.Symbol.Value}'
        self.z_score = 0

    @property
    def DataFrame(self):
        df = pd.concat([self.x.DataFrame.droplevel([0]), self.y.DataFrame.droplevel([0])], axis=1).dropna()
        df.columns = [self.x.Symbol.Value, self.y.Symbol.Value]
        return df
    
    def get_spread(self,return_x,return_y, t, Q):
        """
        t: time start to calculate moving regression (index form)
        we calculate epsilon_t based on regression using data X[t:Q+t] which corresponds to x_{T-t-1}, ... ,  x_{T-t-1-Q}
        Q: lookback period: #timeframes used for fitting the regression

        return: spread / epsilon_{T-t}          
        # Note: T means current time, T-1 means one interval before current time
        """
        # x[t+1:t+Q+1] => getting 
        model = LinearRegression().fit(return_x[t+1 : t+Q+1], return_y[t+1 : t+Q+1])
        spread = return_y[t] - model.coef_ * return_x[t][0] - model.intercept_
        return spread

    def get_slope(self, Q = 10):
        """
        t: time start to calculate moving regression (index form)
        we calculate epsilon_t based on regression using data X[t:Q+t] which corresponds to x_{T-t-1}, ... ,  x_{T-t-1-Q}
        Q: lookback period: #timeframes used for fitting the regression

        return: slope of the regression        
        # Note: T means current time, T-1 means one interval before current time
        """
        df = self.DataFrame.iloc[::-1].pct_change().dropna()

        return_x = df[self.x.Symbol.Value].to_list()
        return_y = df[self.y.Symbol.Value].to_list()

        return_x.reverse()
        return_y.reverse()

        return_x = np.array(return_x).reshape((-1,1))
        return_y = np.array(return_y)

        model = LinearRegression().fit(return_x[1 : Q+1], return_y[1 : Q+1])
        return model.coef_;

    def get_z_score(self, P = 45, Q = 10):
        """
        P: a moving window of period P 
        large P -> estimate the spread is it too big or small (more sample -> more accurate)
        Q: lookback period: #timeframes used for fitting the regression
        return: z-score
        """

        df = self.DataFrame.iloc[::-1].pct_change().dropna()

        return_x = df[self.x.Symbol.Value].to_list()
        return_y = df[self.y.Symbol.Value].to_list()

        return_x.reverse()
        return_y.reverse()

        return_x = np.array(return_x).reshape((-1,1))
        return_y = np.array(return_y)

        all_spread = 0
        all_spread_diff = 0

        for i in range(P): 
            # here i is [0, 1, ..., P-1]
            # we start from 1 to calculate epsilon_{T-1} // spread at X[1]
            all_spread += self.get_spread(return_x, return_y, i+1, Q)
        avg_spread = all_spread / P

        for i in range(P):
            current_spread = self.get_spread(return_x, return_y, i+1, Q)
            all_spread_diff += (current_spread - avg_spread)** 2

        avg_spread_sd = all_spread_diff / P

        self.z_score = ((self.get_spread(return_x, return_y, 0, Q) - avg_spread) / math.sqrt(avg_spread_sd))[0]

        return self.z_score
