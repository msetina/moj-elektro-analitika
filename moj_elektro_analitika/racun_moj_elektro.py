from collections.abc import Iterable
from datetime import date
from logging import Logger

import pandas as pd
from moj_elektro_v1 import MeterReadings


class RacunMojElektro(object):
    def __init__(self, logger: Logger) -> None:
        self._logger = logger
        self.__iter_data: Iterable | None = None

    def __get_po_tarifi(
        self, data: pd.DataFrame, cfgs: dict
    ) -> tuple[pd.DataFrame, dict]:
        dyn_cols = {}
        if "poTarifi" in cfgs:
            for rw in cfgs["poTarifi"]:
                for col in rw.keys():
                    if col != "Tarifa" and col not in dyn_cols:
                        dyn_cols[col] = ["c", "k"]
            pt = pd.json_normalize(cfgs["poTarifi"])
            pt.set_index("Tarifa")
            return pd.merge(data, pt, on="Tarifa", how="left"), dyn_cols
        else:
            return data, dyn_cols

    def __get_po_bloku(self, data: pd.DataFrame, cfgs: dict) -> pd.DataFrame:
        if "poBloku" in cfgs:
            cp = pd.DataFrame(cfgs["poBloku"])
            cp.set_index("Blok")
            return pd.merge(data, cp, on="Blok", how="left")
        else:
            return data

    def _get_VsotaPoEnergiji(
        self, data: pd.DataFrame, dyn_cols: dict, cfgs: dict
    ) -> pd.DataFrame | None:
        if "poTarifi" in cfgs:
            aggregations = {
                "A+": "sum",
                "obracunskaMoc": "last",
            }

            for cl, subs in dyn_cols.items():
                for sub in subs:
                    aggregations.update({cl + "." + sub: "last"})
            grouping = data.groupby(
                [
                    "Leto",
                    "Mesec",
                    "Tarifa",
                ]
            ).agg(aggregations)
            grouping["VsotaPoEnergiji"] = 0
            for col in dyn_cols:
                grouping["Vrednost " + col] = (
                    grouping["A+"] * grouping[col + ".k"] * grouping[col + ".c"]
                )
                grouping["VsotaPoEnergiji"] += grouping["Vrednost " + col]
            return grouping
        else:
            return None

    def _get_Omreznina(
        self, data: pd.DataFrame, cfgs: dict
    ) -> pd.DataFrame | None:
        if "poBloku" in cfgs:
            grouping = data.groupby(
                [
                    "Leto",
                    "Mesec",
                    "Blok",
                ]
            ).agg(
                {
                    "A+": "sum",
                    "Dogovorjena moč": "last",
                    # "Preseganje": "sum",
                    "Cena_P": "last",
                    "Cena_E": "last",
                }
            )
            grouping["Omreznina"] = (
                grouping["Dogovorjena moč"] * grouping["Cena_P"]
                + grouping["A+"] * grouping["Cena_E"]
            )
            return grouping
        else:
            return None

    def _get_Energija_na_mesec(
        self, data: pd.DataFrame, cfgs: dict
    ) -> pd.DataFrame:
        aggregations_fnl = {
            ("A+"): "sum",
            ("VsotaPoEnergiji"): "sum",
        }
        if "poObracunskiMoci" in cfgs:
            aggregations_fnl.update(
                {
                    ("obracunskaMoc"): "last",
                }
            )
        return data.groupby(
            [
                "Leto",
                "Mesec",
            ]
        ).agg(aggregations_fnl)

    def _get_Omreznina_na_mesec(self, data: pd.DataFrame) -> pd.DataFrame:
        return data.groupby(
            [
                "Leto",
                "Mesec",
            ]
        ).agg(
            {
                ("Omreznina"): "sum",
                # ("Preseganje"): "sum",
            }
        )

    def _get_final_sum(self, data: pd.DataFrame, cfgs: dict):
        if "brezTarife" in cfgs:
            for nm, val in cfgs["brezTarife"].items():
                data[nm] = val * data["A+"]

        if "extra" in cfgs:
            for nm, val in cfgs["extra"].items():
                data[nm] = val

        if "poObracunskiMoci" in cfgs:
            for nm, val in cfgs["poObracunskiMoci"].items():
                data[nm] = val * data["obracunskaMoc"]

        data["Sum"] = data["VsotaPoEnergiji"]
        if "Omreznina" in data:
            data["Sum"] += data["Omreznina"]

        if "poObracunskiMoci" in cfgs:
            for nm in cfgs["poObracunskiMoci"].keys():
                data["Sum"] += data[nm]

        if "brezTarife" in cfgs:
            for nm in cfgs["brezTarife"].keys():
                data["Sum"] += data[nm]

        if "extra" in cfgs:
            for nm in cfgs["extra"].keys():
                data["Sum"] += data[nm]

        data["Placilo"] = (data["Sum"]) * 1.22

    def _join_data_frames(
        self, data1: pd.DataFrame, data2: pd.DataFrame
    ) -> pd.DataFrame | None:
        if data1 is not None and data2 is not None:
            return pd.merge(data1, data2, on=["Leto", "Mesec"], how="left")
        elif data1 is not None:
            return data1
        elif data2 is not None:
            return data2
        else:
            return None

    async def __call__(
        self, api_key: str, EIMM: str, frm_d: date, to_d: date, cfgs: dict
    ):

        try:
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

                dataT = self.__get_po_bloku(data_ld, cfgs)

                data2, dyn_cols = self.__get_po_tarifi(dataT, cfgs)

                grup = self._get_Omreznina(data2, cfgs)

                final = None
                if grup is not None:
                    final = self._get_Omreznina_na_mesec(grup)

                grupE = self._get_VsotaPoEnergiji(data2, dyn_cols, cfgs)

                finalE = None
                if grupE is not None:
                    finalE = self._get_Energija_na_mesec(grupE, cfgs)

                if finalE is not None and final is not None:
                    kotDa = self._join_data_frames(final, finalE)
                    if kotDa is not None:
                        self._get_final_sum(kotDa, cfgs)
                        return_vals = kotDa.to_dict("records")
                        for i, ax in enumerate(
                            kotDa.axes[0].to_frame().to_dict("records")
                        ):
                            return_vals[i].update(ax)
                        self.__iter_data = iter(return_vals)
                elif finalE is not None:
                    self._get_final_sum(finalE, cfgs)
                    return_vals = finalE.to_dict("records")
                    for i, ax in enumerate(
                        finalE.axes[0].to_frame().to_dict("records")
                    ):
                        return_vals[i].update(ax)
                    self.__iter_data = iter(return_vals)

        except Exception as e:
            self._logger.error(f"Prišlo je do napake: {e}")
            self.__iter_data = None

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
