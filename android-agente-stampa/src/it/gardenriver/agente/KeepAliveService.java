package it.gardenriver.agente;

import android.app.*;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.wifi.WifiManager;
import android.os.*;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Tiene vivo il processo dell'app e, soprattutto, riceve gli avvisi dei reparti anche con l'app chiusa:
 * ogni ~20 secondi chiede alla funzione telegram-bot i nuovi avvisi (feed_notifiche) e li mostra come notifiche.
 * Parte da sola all'accensione (BootReceiver) e si riavvia se il sistema o l'utente chiudono l'app.
 */
public class KeepAliveService extends Service {
    private PowerManager.WakeLock wl;
    private WifiManager.WifiLock wifi;
    private volatile boolean attivo;
    private Thread poller;
    private static final long PAUSA_MS = 20000L;

    @Override public IBinder onBind(Intent i) { return null; }

    @Override public int onStartCommand(Intent i, int f, int id) {
        NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT >= 26)
            nm.createNotificationChannel(new NotificationChannel("attivo", "Garden Hub attivo", NotificationManager.IMPORTANCE_MIN));
        Notification.Builder nb = Build.VERSION.SDK_INT >= 26 ? new Notification.Builder(this, "attivo") : new Notification.Builder(this);
        PendingIntent pi = PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class),
            Build.VERSION.SDK_INT >= 23 ? PendingIntent.FLAG_IMMUTABLE : 0);
        nb.setContentTitle("Garden Hub attivo").setContentText("Ricevo gli avvisi dei reparti")
          .setSmallIcon(android.R.drawable.stat_notify_sync).setContentIntent(pi).setOngoing(true).setPriority(Notification.PRIORITY_MIN);
        startForeground(2, nb.build());
        if (wl == null) {
            wl = ((PowerManager) getSystemService(Context.POWER_SERVICE)).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "garden:hub");
            wl.acquire();
        }
        if (wifi == null) {
            try {
                wifi = ((WifiManager) getApplicationContext().getSystemService(Context.WIFI_SERVICE)).createWifiLock(WifiManager.WIFI_MODE_FULL, "garden:hub");
                wifi.acquire();
            } catch (Exception e) { wifi = null; }
        }
        avviaSondaggio();
        return START_STICKY;
    }

    /** L'utente toglie l'app dalle recenti: il servizio si ripresenta da solo dopo un attimo. */
    @Override public void onTaskRemoved(Intent root) {
        try {
            Intent r = new Intent(getApplicationContext(), KeepAliveService.class);
            PendingIntent p = Build.VERSION.SDK_INT >= 26
                ? PendingIntent.getForegroundService(this, 1, r, PendingIntent.FLAG_ONE_SHOT | PendingIntent.FLAG_IMMUTABLE)
                : PendingIntent.getService(this, 1, r, PendingIntent.FLAG_ONE_SHOT);
            ((AlarmManager) getSystemService(ALARM_SERVICE)).set(AlarmManager.ELAPSED_REALTIME_WAKEUP, SystemClock.elapsedRealtime() + 1500, p);
        } catch (Exception e) { }
        super.onTaskRemoved(root);
    }

    private synchronized void avviaSondaggio() {
        if (poller != null && poller.isAlive()) return;
        attivo = true;
        poller = new Thread(new Runnable() { public void run() {
            while (attivo) {
                try { sondaggio(); } catch (Exception e) { stato("Avvisi: errore di rete (" + (e.getMessage() == null ? e.toString() : e.getMessage()) + ")"); }
                try { Thread.sleep(PAUSA_MS); } catch (InterruptedException e) { return; }
            }
        } }, "avvisi-feed");
        poller.setDaemon(true);
        poller.start();
    }

    private void stato(String s) { getSharedPreferences("agente", 0).edit().putString("feed_stato", s).apply(); }

    private void sondaggio() throws Exception {
        SharedPreferences sp = getSharedPreferences("agente", 0);
        String url = sp.getString("feed_url", ""), key = sp.getString("feed_key", "");
        if (url.length() == 0 || key.length() == 0) { stato("Avvisi: in attesa della chiave (apri la Hub e accedi)"); return; }
        long visto = sp.getLong("feed_since", 0);
        // Sovrapposizione di 60 secondi: un avviso scritto "in ritardo" non si perde (i doppioni si scartano dall'id)
        JSONObject body = new JSONObject().put("evento", "feed_notifiche").put("since", visto > 0 ? Math.max(1, visto - 60000L) : 0);
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        try {
            c.setConnectTimeout(15000); c.setReadTimeout(20000); c.setRequestMethod("POST"); c.setDoOutput(true);
            c.setRequestProperty("Content-Type", "application/json"); c.setRequestProperty("X-App-Key", key);
            OutputStream o = c.getOutputStream(); o.write(body.toString().getBytes("UTF-8")); o.close();
            int code = c.getResponseCode();
            if (code == 401) { sp.edit().remove("feed_key").apply(); stato("Avvisi: chiave non valida, la richiedo di nuovo"); return; }
            if (code != 200) { stato("Avvisi: risposta " + code); return; }
            BufferedReader br = new BufferedReader(new InputStreamReader(c.getInputStream(), "UTF-8"));
            StringBuilder sb = new StringBuilder(); String riga;
            while ((riga = br.readLine()) != null) sb.append(riga);
            JSONObject r = new JSONObject(sb.toString());
            if (!r.optBoolean("ok")) { stato("Avvisi: " + r.optString("errore")); return; }
            JSONArray items = r.optJSONArray("items");
            if (visto == 0) { sp.edit().putLong("feed_since", r.optLong("now")).putLong("feed_ultimo_ok", System.currentTimeMillis()).apply(); stato("Avvisi: attivo"); return; }
            String viste = sp.getString("feed_ids", "");
            long max = visto; int nuovi = 0;
            for (int i = 0; items != null && i < items.length(); i++) {
                JSONObject it = items.getJSONObject(i);
                String id = it.optString("id"); long ts = it.optLong("ts");
                if (ts > max) max = ts;
                if (id.length() == 0 || viste.contains("|" + id + "|")) continue;
                viste = ("|" + id + "|" + viste);
                if (viste.length() > 1500) viste = viste.substring(0, 1500);
                JSONArray rep = it.optJSONArray("reparti");
                if (rep == null || !Avvisi.miInteressa(this, rep)) continue;
                String titolo = Avvisi.nomeReparto(rep.optString(0)) + (it.optString("titolo").length() > 0 ? " · " + it.optString("titolo") : "");
                Avvisi.mostra(this, titolo, it.optString("testo"), id.hashCode() & 0x7fffffff);
                nuovi++;
            }
            sp.edit().putLong("feed_since", max).putString("feed_ids", viste).putLong("feed_ultimo_ok", System.currentTimeMillis()).apply();
            stato("Avvisi: attivo" + (nuovi > 0 ? " (ultimi: " + nuovi + ")" : ""));
        } finally { c.disconnect(); }
    }

    @Override public void onDestroy() {
        attivo = false;
        if (poller != null) poller.interrupt();
        if (wl != null && wl.isHeld()) wl.release();
        if (wifi != null && wifi.isHeld()) wifi.release();
        super.onDestroy();
    }
}
