"""
Script for handling basic plotting of GITM 3DALL outputs. 

- Can make keograms or maps or any variable in 3DALL
- Ability to set whether to bandpass filter results and plot raw, fit, 
    or % difference between raw & fit
"""


import argparse
import datetime
import gc
from utility_programs.read_routines import GITM
import os
import time
from multiprocessing import Pool

import geopandas
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import signal
from tqdm.auto import tqdm

from utility_programs.plot_help import UT_from_Storm_onset
from utility_programs.plotting_routines import make_a_keo, draw_map
from utility_programs import filters

matplotlib.use("Agg")

np.seterr(divide='ignore')


def main(args):
    """Main plotting routine`.

    Args:
        args (namespace): alll the args

    Raises:
        ValueError: _description_
        ValueError: _description_
    """
    # Set variables
    global world
    world = geopandas.read_file(
        geopandas.datasets.get_path("naturalearth_lowres"))

    global gitm_colnames_friendly
    gitm_colnames_friendly = {
        "Rho": "Total Neutral Density",
        "[O(!U3!NP)]": "O(3P)",
        "[O!D2!N]": "O2",
        "[N!D2!N]": "N2",
        "[N(!U4!NS)]": "N(4S)",
        "[NO]": "NO",
        "[He]": "He",
        "[N(!U2!ND)]": "N(2D)",
        "[N(!U2!NP)]": "N(2P)",
        "[H]": "H",
        "[CO!D2!N]": "CO2",
        "[O(!U1!ND)]": "O(1D)",
        "Temperature": "Temperature",
        "V!Dn!N(east)": "Vn(east)",
        "V!Dn!N(north)": "Vn(north)",
        "V!Dn!N(up)": "Vn(up)",
        "V!Dn!N(up,O(!U3!NP))": "Vn(up,O(3P))",
        "V!Dn!N(up,O!D2!N)": "Vn(up,O2)",
        "V!Dn!N(up,N!D2!N)": "Vn(up,N2)",
        "V!Dn!N(up,N(!U4!NS))": "Vn(up,N(4S))",
        "V!Dn!N(up,NO)": "Vn(up,NO)",
        "V!Dn!N(up,He)": "Vn(up,He)",
        "[O_4SP_!U+!N]": "O(4Sp)+",
        "[NO!U+!N]": "NO+",
        "[O!D2!U+!N]": "O2+",
        "[N!D2!U+!N]": "N2+",
        "[N!U+!N]": "N+",
        "[O(!U2!ND)!U+!N]": "O(2D)+",
        "[O(!U2!NP)!U+!N]": "O(2P)+",
        "[H!U+!N]": "H+",
        "[He!U+!N]": "He+",
        "[e-]": "e-",
        "eTemperature": "eTemperature",
        "iTemperature": "iTemperature",
        "V!Di!N(east)": "Vi(east)",
        "V!Di!N(north)": "Vi(north)",
        "V!Di!N(up)": "Vi(up)", }

    global cols
    if args.cols == 'all':
        cols = gitm_colnames_friendly.keys()
    else:
        cols = []
        for c in args.cols:
            if c in gitm_colnames_friendly.keys():
                cols.append(c)
            else:
                raise ValueError('col %s not found in: \n' %
                                 c, gitm_colnames_friendly.keys())

    # Lon to keo:
    global gitm_keo_lons
    gitm_keo_lons = args.keo_lons

    global lat_lim
    lat_lim = args.lat_lim

    global out_path
    out_path = args.out_path

    global dtime_storm_start
    dtime_storm_start = datetime.datetime.strptime(
        args.dtime_storm_start.ljust(14, '0'), '%Y%m%d%H%M%S')

    # get gitm data!
    global times, gitm_grid, gitm_bins
    times, gitm_grid, gitm_bins = GITM.read_gitm_into_nparrays(
        gitm_dir=args.gitm_data_path,
        dtime_storm_start=dtime_storm_start,
        cols=cols,
        t_start_idx=args.plot_start_delta,
        t_end_idx=args.plot_end_delta)

    print(cols, gitm_bins.shape)

    global hrs_since_storm_onset
    hrs_since_storm_onset = np.array([(i - pd.Timestamp(dtime_storm_start))
                                      / pd.Timedelta('1 hour') for i in times])

    global lats, lons, alts
    lats, lons, alts = (
        np.unique(gitm_grid["latitude"]),
        np.unique(gitm_grid["longitude"]),
        np.unique(gitm_grid["altitude"]))

    if args.gitm_alt_idxs == -1:
        gitm_alt_idxs = list(range(len(alts)))
    else:
        gitm_alt_idxs = args.gitm_alt_idxs

    global fits_gitm
    print("Calculating fits. This will take a moment...")
    fits_gitm = filters.make_fits(gitm_bins)
    print(gitm_bins.shape, fits_gitm.shape)

    # Start plotting.
    if args.keogram:
        print("Making keogram")
        pbar = tqdm(
            total=len(cols) * len(gitm_alt_idxs) * len(gitm_keo_lons),
            desc='keogram making')
        for alt_idx in gitm_alt_idxs:
            for real_lon in gitm_keo_lons:
                for col in cols:
                    call_keos(alt_idx=alt_idx, real_lon=real_lon,
                              namecol=col, save_or_show=args.save_or_show,
                              outliers=args.outliers,
                              lat_lim=lat_lim,
                              figtype=args.figtype, vlims=args.cbarlims)
                    pbar.update()
        pbar.close()

    if args.map:
        print("Making map")
        pbar = tqdm(total=len(gitm_alt_idxs) * len(times) * len(cols),
                    desc='map making')

        for col in cols:
            numcol = cols.index(col)
            for nalt in gitm_alt_idxs:
                for dtime_real in times:
                    call_maps(nalt, dtime_real=dtime_real,
                              numcol=numcol, lat_lim=lat_lim,
                              save_or_show=args.save_or_show,
                              figtype=args.figtype,
                              outliers=args.outliers)
                    pbar.update()
        pbar.close()


def remove_outliers(array):
    arr2 = array.copy()
    # calculate mean, standard deviation, and median over all elements
    mean, std, median = np.mean(arr2), np.std(arr2), np.median(arr2)
    # set outlier threshold (in terms of number of standard deviations)
    outlier_threshold = 5
    outliers = np.logical_or(
        arr2 < mean - outlier_threshold * std, arr2 > mean +
        outlier_threshold * std)  # find outliers
    arr2[outliers] = median  # set outliers to median
    return arr2

# KEO MAKING FUNCTIONS:


def call_keos(
        alt_idx,
        real_lon,
        numcol=None,
        namecol: str = "",
        save_or_show="show",
        return_figs=False,
        figtype="all",
        lat_lim=90,
        outliers=False,
        vlims=None):

    if numcol is None and namecol != "":
        numcol = cols.index(namecol)
    elif namecol == "" and numcol is not None:
        namecol = cols[numcol]
    elif numcol is None and namecol == "":
        raise ValueError("either namecol or numcol must be specified!")

    if vlims is None:

        vmin_bins = np.min(gitm_bins[:, numcol, :, :, alt_idx])
        vmax_bins = np.max(gitm_bins[:, numcol, :, :, alt_idx])

        vmin_fits = np.min(fits_gitm[:, numcol, :, :, alt_idx])
        vmax_fits = np.max(fits_gitm[:, numcol, :, :, alt_idx])

        vmin_diffs = np.min(100 * (fits_gitm[:, numcol, :, :, alt_idx]
                                   - gitm_bins[:, numcol, :, :, alt_idx])
                            / gitm_bins[:, numcol, :, :, alt_idx])
        vmax_diffs = np.max(100 * (fits_gitm[:, numcol, :, :, alt_idx]
                                   - gitm_bins[:, numcol, :, :, alt_idx])
                            / gitm_bins[:, numcol, :, :, alt_idx])

    else:
        vmin = -vlims
        vmax = vlims
        vmin_bins = vmin
        vmax_bins = vmax
        vmin_diffs = vmin
        vmax_diffs = vmax
        vmin_fits = vmin
        vmax_fits = vmax

    # get data.
    lon_idx = np.argmin(np.abs(lons - real_lon))
    real_lon = lons[lon_idx]
    data = gitm_bins[:, numcol, lon_idx, :, alt_idx].copy()
    bandpass = fits_gitm[:, numcol, lon_idx, :, alt_idx].copy()
    if np.sum(data) == 0:
        raise ValueError("No data at this altitude and longitude!",
                         data.shape, real_lon, namecol, numcol)
    real_alt = alts[alt_idx]
    percent = 100 * (data - bandpass) / bandpass

    if outliers:
        data = remove_outliers(data)
        bandpass = remove_outliers(bandpass)
        percent = remove_outliers(percent)

    made_plot = False

    if figtype == "all" or "filt" in figtype:
        # plain bandpass filter
        title = "Keogram of %s along %i deg Longitude at %i km" % (
            gitm_colnames_friendly[namecol].replace(
                "(", "[").replace(")", "]"),
            real_lon,
            round(real_alt / 1000, 0),)
        color_label = "Bandpass filter"
        # print(out_path, real_alt, real_lon, namecol)
        # print(int(real_alt/1000,0), int(real_lon))
        fname = os.path.join(
            out_path, 'keo',
            "bandpass",
            str(int(real_alt / 1000)),
            "lon" + str(int(real_lon)),
            gitm_colnames_friendly[namecol] + ".png",)
        make_a_keo(
            arr=bandpass,
            title=title,
            cbarlims=(vmin_fits, vmax_fits),
            cbar_name=color_label,
            ylims=[-lat_lim, lat_lim],
            save_or_show=save_or_show,
            fname=fname,
            extent=[min(hrs_since_storm_onset), max(hrs_since_storm_onset), -90, 90],)
        made_plot = True

    if figtype == "all" or "raw" in figtype:
        # plain raw data
        title = "Keogram of %s along %i deg Longitude at %i km" % (
            gitm_colnames_friendly[namecol].replace(
                "(", "[").replace(")", "]"),
            real_lon,
            round(real_alt / 1000, 0),)
        color_label = "Raw data"
        fname = os.path.join(
            out_path, 'keo',
            "raw",
            str(int(real_alt / 1000)),
            "lon" + str(int(real_lon)),
            gitm_colnames_friendly[namecol] + ".png",)
        make_a_keo(
            arr=data,
            title=title,
            ylims=[-lat_lim, lat_lim],
            cbarlims=(vmin_bins, vmax_bins),
            cbar_name=color_label,
            save_or_show=save_or_show,
            fname=fname,
            extent=[min(hrs_since_storm_onset), max(hrs_since_storm_onset), -90, 90],)
        made_plot = True

    if figtype == "all" or "diff" in figtype:
        title = "Keogram of %s along %i deg Longitude at %i km" % (
            gitm_colnames_friendly[namecol].replace(
                "(", "[").replace(")", "]"),
            real_lon,
            round(real_alt / 1000, 0),)
        color_label = "% over bandpass filter"
        fname = os.path.join(
            out_path, 'keo',
            "percent-over-filter",
            str(int(real_alt / 1000)),
            "lon" + str(int(real_lon)),
            gitm_colnames_friendly[namecol] + ".png",)
        make_a_keo(
            arr=percent,
            title=title,
            ylims=[-lat_lim, lat_lim],
            cbarlims=(vmin_diffs, vmax_diffs),
            cbar_name=color_label,
            save_or_show=save_or_show,
            fname=fname,
            extent=[min(hrs_since_storm_onset), max(hrs_since_storm_onset), -90, 90],)
        made_plot = True

    if not made_plot:
        print("nothing made")


def call_maps(
        alt_idx,
        dtime_real=None,
        dtime_index=None,
        numcol=None,
        namecol=None,
        save_or_show="show",
        return_figs=False,
        figtype="all",
        lat_lim=90,
        diffs=[1, 2, 3, 5, 10, 30, 50],
        outliers=False):

    # Make sure inputs are correct. either the index or actual value of the
    #    datetime and column to plot can be specified (or both).
    if numcol is None and namecol is not None:
        numcol = cols.index(namecol)
    elif namecol is None and numcol is not None:
        namecol = cols[numcol]
    elif numcol is None and namecol is None:
        raise ValueError("either namecol or numcol must be specified!")

    if dtime_real is None and dtime_index is not None:
        dtime_real = times[dtime_index]
    elif dtime_index is None and dtime_real is not None:
        dtime_index = np.argmin(np.abs(np.array(times) - dtime_real))
    elif dtime_real is None and dtime_index is None:
        raise ValueError("either dtime_index or dtime_real must be specified!")

    # get colorbar limits.
    vmin_bins = np.min(gitm_bins[:, numcol, :, :, alt_idx])
    vmax_bins = np.max(gitm_bins[:, numcol, :, :, alt_idx])

    vmin_fits = np.min(fits_gitm[:, numcol, :, :, alt_idx])
    vmax_fits = np.max(fits_gitm[:, numcol, :, :, alt_idx])

    if type(diffs) != list:

        vmin_diffs = np.min(100 * (fits_gitm[:, numcol, :, :, alt_idx]
                                   - gitm_bins[:, numcol, :, :, alt_idx])
                            / gitm_bins[:, numcol, :, :, alt_idx])
        vmax_diffs = np.max(100 * (fits_gitm[:, numcol, :, :, alt_idx]
                                   - gitm_bins[:, numcol, :, :, alt_idx])
                            / gitm_bins[:, numcol, :, :, alt_idx])

    # get data.
    raw = gitm_bins[dtime_index, numcol, :, :, alt_idx].copy()
    bandpass = fits_gitm[dtime_index, numcol, :, :, alt_idx].copy()
    real_alt = alts[alt_idx]
    percent = 100 * (raw - bandpass) / raw

    if outliers:
        raw = remove_outliers(raw)
        bandpass = remove_outliers(bandpass)
        percent = remove_outliers(percent)

    made_plot = False

    # raw map
    if figtype == "all" or "raw" in figtype:
        title = (
            gitm_colnames_friendly[namecol]
            + " at "
            + str(round(float(real_alt) / 1000, 0))
            + " km at "
            + UT_from_Storm_onset(dtime_real, dtime_storm_start)
            + " from Storm Start")
        fname = os.path.join(
            out_path, 'maps',
            "raw",
            str(int(real_alt / 1000)),
            gitm_colnames_friendly[namecol],
            str(dtime_index).rjust(3, "0") + ".png",)
        cbarlims = [vmin_bins, vmax_bins]
        draw_map(raw, title=title, cbarlims=cbarlims, fname=fname,
                 save_or_show=save_or_show, ylims=[-lat_lim, lat_lim])
        made_plot = True

    # filter map
    if figtype == "all" or "filt" in figtype:
        title = (
            gitm_colnames_friendly[namecol]
            + " at "
            + str(round(float(real_alt) / 1000, 0))
            + " km at "
            + UT_from_Storm_onset(dtime_real, dtime_storm_start)
            + " from Storm Start")
        fname = os.path.join(
            out_path, 'maps',
            "bandpass",
            str(int(real_alt / 1000)),
            gitm_colnames_friendly[namecol],
            str(dtime_index).rjust(3, "0") + ".png",)
        cbarlims = [vmin_fits, vmax_fits]
        cbar_label = "Bandpass Filtered " + gitm_colnames_friendly[namecol]
        draw_map(
            data_arr=bandpass,
            title=title,
            cbarlims=cbarlims,
            save_or_show=save_or_show,
            cbar_label=cbar_label,
            fname=fname,
            ylims=[-lat_lim, lat_lim],)
        made_plot = True

    # diffs
    if figtype == "all" or "diff" in figtype:
        title = (
            gitm_colnames_friendly[namecol]
            + " at "
            + str(round(float(real_alt) / 1000, 0))
            + " km at "
            + UT_from_Storm_onset(dtime_real, dtime_storm_start)
            + " from Storm Start")
        if type(diffs) == list:
            for v_lim in diffs:
                fname = os.path.join(
                    out_path, 'maps',
                    "diff",
                    str(int(real_alt / 1000)),
                    gitm_colnames_friendly[namecol],
                    str(v_lim),
                    str(dtime_index).rjust(3, "0") + ".png",)
                cbarlims = [-v_lim, v_lim]
                cbar_label = "% over Background"
                draw_map(
                    data_arr=percent,
                    title=title,
                    cbarlims=cbarlims,
                    save_or_show=save_or_show,
                    cbar_label=cbar_label,
                    fname=fname,
                    ylims=[-lat_lim, lat_lim],)
        else:
            fname = os.path.join(
                out_path, 'maps'
                "diff",
                str(int(real_alt / 1000)),
                gitm_colnames_friendly[namecol],
                str(dtime_index).rjust(3, "0") + ".png",)
            cbarlims = [vmin_diffs, vmax_diffs]
            cbar_label = "% over Background"
            draw_map(
                data_arr=percent,
                title=title,
                cbarlims=cbarlims,
                save_or_show=save_or_show,
                cbar_label=cbar_label,
                fname=fname,
                ylims=[-lat_lim, lat_lim],)
            made_plot = True

    if not made_plot:
        print("No plot made. Check figtype input.")

    plt.close("all")
    gc.collect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Make plots of GITM data at a given altitude and time.")

    parser.add_argument(
        'dtime_storm_start',
        help='Datetime of storm start. Format YYYYMMDDHHmmss',
        action='store')

    parser.add_argument(
        '-gitm_data_path', type=str,
        help='Path to gitm data', default='./gitm_dir', action='store')

    parser.add_argument(
        '--out_path', type=str,
        help='path to where plots are saved', default='./', action='store')

    parser.add_argument(
        '--cols', nargs="+", type=str,
        help='Which columns to plot. Default: all', default='all')

    parser.add_argument(
        '--plot_start_delta', type=int,
        action='store', default=-1, required=False)

    parser.add_argument(
        '--plot_end_delta', type=int,
        action='store', default=-1, required=False)

    parser.add_argument(
        '--save_or_show', type=str,
        action='store', default='save', required=False,
        help='Save or show plots. Default: save')

    parser.add_argument(
        '--figtype', type=str, action='store', default='all',
        help='Which type of plot to make.' +
        'Options: raw, filt, diffs. Default: all')

    parser.add_argument(
        "--lat_lim", type=float, default=90, action='store',
        help="limit plotted latitudes to this +/- in keos & maps")

    parser.add_argument(
        '--cbarlims', type=int,
        help='Set the limits of the colorbars on the plots made.',
        action='store', default=None, required=False)

    parser.add_argument(
        "-f", "--file-type", type=str, nargs="+",
        default="3DALL*",
        help="which filetype to plot, e.g. (default:) 3DALL* or 2DANC*",)

    parser.add_argument(
        "-o", "--outliers", action="store_true",
        help="do you want to remove outliers")

    parser.add_argument(
        "-k", "--keogram", action="store_true",
        help="do you want to make a keogram?")

    parser.add_argument(
        '--keo_lons', type=float, nargs="+",
        action='store', default=[-90, 2, 90, -178], required=False,
        help='Lons to plot keograms for. Default: -90,2,90,-178')

    parser.add_argument(
        '--gitm_alt_idxs', type=int, nargs="*",
        default=[5, 10, 15, 22, 30, 45],
        help='Which altitudes to plot. Default: 5,10,15,22,30,45')

    parser.add_argument(
        "-m", "--map", action="store_true", help="do you want to make a map?")

    args = parser.parse_args()

    main(args)