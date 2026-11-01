**Osirus for MPC 0.2.9**: no more crackle on heavy chords, favourites in MPC's PRESET menu, and `.syx` banks.

- **Headroom.** Heavy, high-velocity chords made the emulated Virus clip its own output (the crackle some of you heard, with DROPOUTS at 0). Osirus now keeps the Virus's channel volume at about 100 and gives the difference back after it, with a soft limiter, so ordinary patches sound as loud as before and hot ones no longer clip. There is no new control; OUTPUT LEVEL % is unchanged. PATCH VOLUME still helps on a very hot patch.
- **Favourites.** On the BANKS page, **+FAV** saves the current patch (with your knob changes) from any bank and **-FAV** removes the favourite that is loaded. Up to 64, kept in `osirus/favourites.dat`, listed in MPC's PRESET menu. A favourite made on another ROM model (A, B, C) is shown as `Name <C>` and is not loaded.
- **`.syx` banks.** SysEx bank dumps saved as `.syx` in `osirus/banks/` now load, as `.mid` ones do.
- A keyboard's volume slider (CC 7) can no longer undo the headroom.
- If the labels look old after updating, restart MPC (it caches skin pictures).

If it still crackles, please send: the patch name, your MPC model and OS version, the buffer size, and the PLAY page STATS line (DROPOUTS n). DROPOUTS above 0 is a different problem from clipping.

No ROM is included. GPL-3.0, see CREDITS.md. Not affiliated with or endorsed by Access Music.
