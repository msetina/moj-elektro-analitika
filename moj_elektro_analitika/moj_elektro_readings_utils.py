import pandas as pd


def calc_presezki(data: pd.DataFrame) -> pd.DataFrame:
    data.loc[
        data["P+"] > data["Dogovorjena moč"],
        "Preseganje",
    ] = (
        data["P+"] - data["Dogovorjena moč"]
    )
    rez = data[data["Preseganje"] > 0]
    return rez[
        [
            "Merilno mesto",
            "dt",
            "P+",
            "Dogovorjena moč",
            "Blok",
            "Preseganje",
        ]
    ]


def calc_dogovorjena_moc(data: pd.DataFrame) -> pd.Series:
    return data.groupby(
        [
            "Blok",
        ]
    )[
        "P+"
        # ].nlargest(3)
    ].apply(lambda grp: grp.nlargest(3).agg("mean"))


def calc_poraba_over_slots(data: pd.DataFrame, slot_name: str) -> pd.DataFrame:
    grouping = [
        "Leto",
        "Mesec",
    ]
    grouping.append(slot_name)
    return data.groupby(grouping).agg(
        {
            "A+": "sum",
            "P+": ["max", "min", "mean"],
        }
    )