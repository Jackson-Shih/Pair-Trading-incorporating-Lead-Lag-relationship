#region imports
from AlgorithmImports import *
#endregion

class TradingPair(object):

    def __init__(self, ticket_x, ticket_y, z_score):
        self.ticket_x = ticket_x
        self.ticket_y = ticket_y
        self.z_score = z_score
