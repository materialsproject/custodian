#!/usr/bin/env python

import abc

class ErrorHandler(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def check(self):
        pass

    @abc.abstractmethod
    def correct(self):
        pass

