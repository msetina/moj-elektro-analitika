from collections.abc import Iterable
from datetime import date
from logging import Logger

import pandas as pd
from moj_elektro_v1 import MeterReadings

from moj_elektro_analitika.moj_elektro_readings_utils import (
    calc_dogovorjena_moc,
)


class DogovorjenaMocMojElektro(object):
    def __init__(self, logger: Logger) -> None:
        self._logger = logger
        self.__iter_data: Iterable | None = None
        self.__error: BaseException | None = None

    def get_error(self):
        return self.__error

    async def __call__(self, api_key: str, EIMM: str, frm_d: date, to_d: date):
        try:
            self.__error = None
            async with MeterReadings.get_session() as session:
                rdngs_lst = []
                async for rdngs in MeterReadings.generate_readings(
                    session,
                    api_key,
                    EIMM,
                    frm_d,
                    to_d,
                    ["A+", "P+"],
                    self._logger,
                ):
                    rdngs_lst.extend(rdngs)

                data_ld = pd.DataFrame(rdngs_lst)
                dog_moc = calc_dogovorjena_moc(data_ld)
                self.__iter_data = iter([dog_moc.to_dict()])

        except Exception as e:
            self.__error = e
            self._logger.error(f"Prišlo je do napake: {e}")
            self.__iter_data = None
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.__iter_data is None:
            raise StopAsyncIteration()
        else:
            try:
                return next(self.__iter_data)
            except StopIteration:
                raise StopAsyncIteration()
