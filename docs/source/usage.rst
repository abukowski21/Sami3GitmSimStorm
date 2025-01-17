Post-Processing
###############



.. note:: 
    These steps will assume you have installed the package and have the required python packages installed. You can check your installed conda environments with:
    ``conda info --envs``
    And assuming you have installed the package with conda, you can activate it with:
    ``conda activate SAMI3-GITM-python`` (Adapt this last command if you have done the installation differently)


GITM Outputs
============


GITM natively writes files out at each time-step, for each worker. These are in the ``run/UA/data`` directory and are stored as ``*.header`` and ``*.b####`` files (one header for each time-step and one .b#### file for each worker, at each time-step). These are not meant to be interfaced with by the user. To run any of these scripts, you need to process them with ``pGITM``. This is located in your ``run/`` directory. 

To create a file for each time-step, combining the output ``3DALL``, ``2DANC``, etc. files, you will run:

.. code-block:: bash

    python PostProcessModelResults.py -gitm /path/to/gitm/run/UA/data/ -out /path/to/output/directory/ 

A progress bar will be displayed. You can turn this off with the ``--no_progress`` flag.

.. note::
    By default, GITM's "Ghost Cells" are dropped. You can include them with the ``-g`` or ``ghost_cells`` flag.

After things are done processing, a NetCDF file will be created for each time-step. For longer runs, often it is easier to have a single file for the entire run. This speeds up file reads and with Dask_ we do not have to worry about memory usage. To create a single file for the entire run:

.. _Dask: https://docs.xarray.dev/en/stable/user-guide/dask.html

.. code-block:: bash

    python PostProcessModelResults.py -gitm /path/to/gitm/run/UA/data/ -out /path/to/output/directory/ -single_file RUN_NAME


``_GITM.nc`` will be appended to RUN_NAME. So if you want the output file to be saved as ``/Users/me/Documents/GITM_RUNS/test_GITM.nc``, you would say ``[...] -out /Users/me/Documents/GITM_RUNS/ -single_file test``

.. note::
    Writing GITM outputs to a single file is incredibly memory and I/O intense. To solve this, temporary files are written to a temp directory (in the out_dir) folder. You can change this to another location if you would like with the ``tmp_dir`` flag.


Additional arguments are available to unlock more complex features. Run ``python PostProcessModelResults.py -h`` or  to see them all.


SAMI3 Outputs
=============


SAMI3 natively writes one file for each variable. Longer model runs do not result in more files, but rather longer files. These files are indexed with ``(nz, nf, nlt, nt)`` according to the user settings, where ``nz`` is the index of the grid point (along the field line), ``nf`` is the index of the field line (along the longitude), ``nlt`` is the number of magnetic longitudes, and ``nt`` is the time step.

We automatically read the user-specified resolution of the model run but **do not** read in the start time of the simulation. This must be supplied by the user. SAMI3 files have two processing options.

.. note::
    By default, both `raw` and `regrid` files are written when a user runs PostProcessModelResults.py. 

Writing raw SAMI3 Outputs to NetCDF
-----------------------------------

To write the raw SAMI3 outputs to a single NetCDF file, you will run:

.. code-block:: bash

    python PostProcessModelResults.py -sami3 /path/to/sami3/run/ -out /path/to/output/directory/ --dtime_sim_start 20110521 --sami_type raw --single_file RUN_NAME

These outputs retain the same indexing as the original files. 

Regridding SAMI3 Outputs
------------------------

It is often more useful to have SAMI3 outputs on a regular grid. This can be done with the ``--sami_type regrid`` flag. This will regrid the SAMI3 outputs to a regular grid, using Scipy's LinearNDInterpolator_

.. _LinearNDInterpolator: https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.LinearNDInterpolator.html


To keep things approachable and streamlined, PostProcessModelResults.py does not have very robust options with the regridding. From the command line, the ``RegridSami.py`` script has a lot more functionality accessible to the user. For example, you can specify the grid yourself with:

.. code-block:: bash

    python RegridSami.py /path/to/sami3/run/ --out_path /path/to/output/directory/ --dtime_sim_start 20110521 --run_name RUN_NAME --custom_grid

There is also the option to "fly a satellite through" the model outputs, interpolating the model outputs to the satellite location. The simulated satellite measurements are calculated at **every** time that we have model data for. Thus, each variable in the output data (in NetCDF format) is indexed with ``(sat_step, sami_time)``. The exception for this is ``(glat, glon, alt, sat_time)``, which are only indexed with ``sat_step``. To simulate satellite measurements, ensure "lat, lon, alt" are columns in (and in deg/km units) a .csv file and run:

.. code-block:: bash

    python RegridSami.py /path/to/sami3/run/ --out_path /path/to/output/directory/ --dtime_sim_start 20110521 --run_name RUN_NAME --input_coord_file /path/to/satellite/file.csv


Using in a Python script
========================

These scripts are not available on conda-forge or via pip. There is no current plan to make them available on a python package manager, or to make these scripts install-able in a python environment. 

Instead, to interface with any script available in a standalone python script, you need to add the path to this package to your ``$PATH``. This is easy, don't worry!! At the top of your file (or Jupyter Notebook)


.. code-block:: python
    
    import sys
    sys.path.append('/path/to/SAMI3-GITM-python/')
    from RegridSami import main
    from utility_programs import filters

For example, in the ``REFERENCE-examplenotebooks/`` folder, most notebooks have a line at the top with ``sys.path.append(../)``. 


To get help on any function, you can use the ``help()`` function or ``?`` in Jupyter Notebooks. For example, to get help on the ``main()`` function in ``RegridSami.py``:

.. code-block:: python

    help(RegridSami.main)


.. note:: 
    For more examples and walkthroughs on usage, see the :ref:`plotting` or :ref:`rw_data` section. There are also more examples in the REFERENCE-examplenotebooks section.
