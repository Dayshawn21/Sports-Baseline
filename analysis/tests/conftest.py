import matplotlib

# Off-screen rendering; the Tk window backend is flaky without a display.
matplotlib.use("Agg")
