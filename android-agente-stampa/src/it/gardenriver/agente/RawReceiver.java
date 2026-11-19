package it.gardenriver.agente;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Solo per prove: stampa una sequenza di byte (esadecimale) sulla stampante integrata. */
public class RawReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context c, Intent i) {
        final String hex = i.getStringExtra("hex");
        if (hex == null) return;
        new Thread(new Runnable() { public void run() {
            try {
                String h = hex.replaceAll("[^0-9a-fA-F]", "");
                byte[] b = new byte[h.length() / 2];
                for (int k = 0; k < b.length; k++) b[k] = (byte) Integer.parseInt(h.substring(2 * k, 2 * k + 2), 16);
                MainActivity.stampaGrezzo(b);
            } catch (Exception e) { android.util.Log.e("RAW", String.valueOf(e)); }
        } }).start();
    }
}
