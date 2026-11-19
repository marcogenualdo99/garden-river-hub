package it.gardenriver.agente;

import android.app.*;
import android.content.Context;
import android.content.Intent;
import android.os.*;

/** Tiene vivo il processo dell'app (e la pagina Hub con gli avvisi) anche con lo schermo spento o l'app in secondo piano. */
public class KeepAliveService extends Service {
    private PowerManager.WakeLock wl;

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
        return START_STICKY;
    }

    @Override public void onDestroy() {
        if (wl != null && wl.isHeld()) wl.release();
        super.onDestroy();
    }
}
