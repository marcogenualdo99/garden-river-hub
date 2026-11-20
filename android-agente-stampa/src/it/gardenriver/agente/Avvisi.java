package it.gardenriver.agente;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import org.json.JSONArray;

/** Avvisi di reparto come notifiche Android: usati dalla pagina (ponte JS) e dal servizio nativo (app chiusa). */
public final class Avvisi {
    private Avvisi() { }

    private static String ultimaChiave = "";
    private static long ultimaTs = 0;

    /** Nome leggibile del reparto; i gruppi per autista ("navetta:nome") valgono come il reparto base. */
    public static String nomeReparto(String id) {
        if (id == null) return "";
        if (id.indexOf(':') > 0) id = id.substring(0, id.indexOf(':'));
        switch (id) {
            case "manutenzione": return "Manutenzione";
            case "navetta": return "Navetta";
            case "pulizie": return "Pulizie";
            case "reception": return "Reception";
            case "ristorazione": return "Ristorazione";
            case "market": return "Market";
            default: return id;
        }
    }

    private static String nomeBase(String id) { return id != null && id.indexOf(':') > 0 ? id.substring(0, id.indexOf(':')) : id; }

    /** Reparti scelti dall'operatore nella Hub (null = non ancora scelti: tutti). */
    public static boolean miInteressa(Context c, JSONArray repartiAvviso) {
        String s = c.getSharedPreferences("agente", 0).getString("reparti", null);
        if (s == null) return repartiAvviso != null && repartiAvviso.length() > 0;
        try {
            JSONArray mie = new JSONArray(s);
            for (int i = 0; i < repartiAvviso.length(); i++)
                for (int j = 0; j < mie.length(); j++) if (nomeBase(repartiAvviso.optString(i)).equals(mie.optString(j))) return true;
        } catch (Exception e) { return true; }
        return false;
    }

    /** Il primo reparto dell'avviso che interessa a questo operatore (altrimenti il primo dell'elenco). */
    public static String repartoPerTitolo(Context c, JSONArray repartiAvviso) {
        String s = c.getSharedPreferences("agente", 0).getString("reparti", null);
        try {
            if (s != null) {
                JSONArray mie = new JSONArray(s);
                for (int i = 0; i < repartiAvviso.length(); i++)
                    for (int j = 0; j < mie.length(); j++) {
                        String a = repartiAvviso.optString(i), b = mie.optString(j);
                        if (a.equals(b) || (a.indexOf(':') > 0 && a.substring(0, a.indexOf(':')).equals(b))) return a;
                    }
            }
        } catch (Exception e) { }
        return repartiAvviso.length() > 0 ? repartiAvviso.optString(0) : "";
    }

    /** true se il servizio nativo sta ricevendo gli avvisi (ultimo controllo riuscito da meno di 2 minuti). */
    public static boolean feedAttivo(Context c) {
        SharedPreferences sp = c.getSharedPreferences("agente", 0);
        return sp.getString("feed_key", "").length() > 0 && System.currentTimeMillis() - sp.getLong("feed_ultimo_ok", 0) < 120000L;
    }

    public static synchronized void mostra(Context c, String titolo, String testo, int id) {
        // Stesso avviso arrivato da due strade (pagina e servizio): una sola notifica
        String chiave = titolo + "|" + testo;
        long ora = System.currentTimeMillis();
        if (chiave.equals(ultimaChiave) && ora - ultimaTs < 60000L) return;
        ultimaChiave = chiave; ultimaTs = ora;
        NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT >= 26)
            nm.createNotificationChannel(new NotificationChannel("avvisi", "Avvisi reparti", NotificationManager.IMPORTANCE_HIGH));
        PendingIntent pi = PendingIntent.getActivity(c, 0, new Intent(c, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            Build.VERSION.SDK_INT >= 23 ? PendingIntent.FLAG_IMMUTABLE : 0);
        Notification.Builder nb = Build.VERSION.SDK_INT >= 26 ? new Notification.Builder(c, "avvisi") : new Notification.Builder(c);
        nb.setContentTitle(titolo).setContentText(testo).setStyle(new Notification.BigTextStyle().bigText(testo))
          .setSmallIcon(android.R.drawable.ic_popup_reminder).setContentIntent(pi).setAutoCancel(true)
          .setDefaults(Notification.DEFAULT_ALL).setPriority(Notification.PRIORITY_HIGH);
        nm.notify(id, nb.build());
    }
}
