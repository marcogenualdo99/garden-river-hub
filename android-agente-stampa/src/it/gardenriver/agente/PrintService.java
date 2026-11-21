package it.gardenriver.agente;

import android.app.*;
import android.content.Context;
import android.content.SharedPreferences;
import android.os.*;
import android.util.Base64;
import org.json.*;
import java.io.*;
import java.net.*;
import javax.net.ssl.HttpsURLConnection;

/** Servizio in primo piano: chiede alla Cloud Function i lavori in coda e li manda alla stampante (TCP 9100). */
public class PrintService extends Service {
    private volatile boolean run;
    private Thread th;
    private PowerManager.WakeLock wl;

    @Override public IBinder onBind(android.content.Intent i) { return null; }

    @Override public int onStartCommand(android.content.Intent i, int f, int id) {
        String ch = "agente";
        NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT >= 26)
            nm.createNotificationChannel(new NotificationChannel(ch, "Agente stampa", NotificationManager.IMPORTANCE_LOW));
        Notification.Builder nb = Build.VERSION.SDK_INT >= 26 ? new Notification.Builder(this, ch) : new Notification.Builder(this);
        PendingIntent pi = PendingIntent.getActivity(this, 0, new android.content.Intent(this, MainActivity.class),
            Build.VERSION.SDK_INT >= 23 ? PendingIntent.FLAG_IMMUTABLE : 0);
        nb.setContentTitle("Garden Hub - agente stampa attivo").setContentText("In ascolto delle stampe")
          .setSmallIcon(android.R.drawable.stat_sys_upload).setContentIntent(pi).setOngoing(true);
        startForeground(1, nb.build());
        if (th == null || !th.isAlive()) {
            PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
            wl = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "agente:stampa");
            wl.acquire();
            run = true;
            th = new Thread(new Runnable() { public void run() { ciclo(); } });
            th.start();
        }
        return START_STICKY;
    }

    @Override public void onDestroy() {
        run = false;
        if (th != null) th.interrupt();
        if (wl != null && wl.isHeld()) wl.release();
        super.onDestroy();
    }

    private void stato(String s) {
        getSharedPreferences("agente", 0).edit().putString("stato", s).apply();
    }

    private static String ora() { return new java.text.SimpleDateFormat("HH:mm:ss").format(new java.util.Date()); }

    private JSONObject chiama(String url, String token, JSONObject body) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(8000); c.setReadTimeout(15000);
        c.setRequestMethod("POST"); c.setDoOutput(true);
        c.setRequestProperty("Content-Type", "application/json");
        c.setRequestProperty("X-Agente-Token", token);
        OutputStream o = c.getOutputStream();
        o.write(body.toString().getBytes("UTF-8")); o.close();
        int code = c.getResponseCode();
        InputStream is = code >= 400 ? c.getErrorStream() : c.getInputStream();
        ByteArrayOutputStream bo = new ByteArrayOutputStream();
        byte[] buf = new byte[4096]; int n;
        while (is != null && (n = is.read(buf)) > 0) bo.write(buf, 0, n);
        if (code == 401) throw new Exception("token non valido");
        if (code >= 400) throw new Exception("HTTP " + code);
        return new JSONObject(bo.toString("UTF-8"));
    }

    private void invia(String ip, byte[] dati) throws Exception {
        Socket s = new Socket();
        try {
            s.connect(new InetSocketAddress(ip, 9100), 5000);
            OutputStream o = s.getOutputStream();
            o.write(dati); o.flush();
        } finally { try { s.close(); } catch (Exception e) { } }
    }

    private void ciclo() {
        int stampati = 0;
        while (run) {
            SharedPreferences sp = getSharedPreferences("agente", 0);
            String url = sp.getString("url", ""), token = sp.getString("token", "");
            long attesa = 5000;
            try {
                if (url.length() == 0 || token.length() == 0) throw new Exception("URL o token mancanti");
                JSONObject r = chiama(url, token, new JSONObject().put("azione", "prendi"));
                JSONArray lav = r.optJSONArray("lavori");
                for (int i = 0; lav != null && i < lav.length(); i++) {
                    JSONObject j = lav.getJSONObject(i);
                    JSONObject es = new JSONObject().put("azione", "esito").put("id", j.getString("id"));
                    try {
                        if ("interna".equals(j.getString("ip"))) {
                            byte[] d = EposConverter.converti(j.getString("xml"), 32, 42, 384);
                            byte[] tutto = new byte[d.length + 6];
                            System.arraycopy(d, 0, tutto, 0, d.length);
                            for (int k = d.length; k < tutto.length; k++) tutto[k] = '\n';   // spazio per lo strappo
                            MainActivity.inviaInterna(tutto);
                        } else {
                            invia(j.getString("ip"), Base64.decode(j.getString("dati"), Base64.DEFAULT));
                        }
                        es.put("ok", true); stampati++;
                    } catch (Exception e) {
                        es.put("ok", false).put("errore", "stampante " + j.optString("ip") + ": " + e.getMessage());
                    }
                    try { chiama(url, token, es); } catch (Exception e) { }
                }
                stato("Attivo - ultimo controllo " + ora() + " - stampe inviate: " + stampati);
            } catch (Exception e) {
                stato("Errore (" + ora() + "): " + e.getMessage());
                attesa = 15000;
            }
            try { Thread.sleep(attesa); } catch (InterruptedException e) { }
        }
    }
}
