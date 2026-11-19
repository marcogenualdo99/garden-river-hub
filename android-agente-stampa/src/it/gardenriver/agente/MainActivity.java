package it.gardenriver.agente;

import android.app.Activity;
import android.app.Dialog;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Message;
import android.view.KeyEvent;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.*;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.Socket;
import org.json.JSONObject;

/** Garden Hub dentro al Sunmi: WebView a schermo intero + stampa diretta + agente di coda in background. */
public class MainActivity extends Activity {
    private WebView web;
    private Dialog figlia;
    private WebView webFiglia;
    private ValueCallback<Uri[]> chooser;
    private boolean backLungo;
    private static final int REQ_FILE = 11;

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        if (Build.VERSION.SDK_INT >= 33) requestPermissions(new String[]{"android.permission.BLUETOOTH_CONNECT", "android.permission.POST_NOTIFICATIONS"}, 2);
        else if (Build.VERSION.SDK_INT >= 31) requestPermissions(new String[]{"android.permission.BLUETOOTH_CONNECT"}, 2);
        SharedPreferences sp = getSharedPreferences("agente", 0);
        if (sp.getBoolean("attivo", false) && sp.getString("token", "").length() > 0) avviaServizio();

        web = new WebView(this);
        configura(web);
        web.addJavascriptInterface(new Ponte(), "GRNativo");
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> cb, FileChooserParams p) {
                if (chooser != null) chooser.onReceiveValue(null);
                chooser = cb;
                boolean immagine = false;
                for (String t : p.getAcceptTypes()) if (t != null && t.startsWith("image")) immagine = true;
                try {
                    if (immagine && p.isCaptureEnabled()) { scattaFoto(); return true; }
                    startActivityForResult(p.createIntent(), REQ_FILE);
                }
                catch (Exception e) { chooser.onReceiveValue(null); chooser = null; return true; }
                return true;
            }
            @Override public boolean onCreateWindow(WebView v, boolean dialog, boolean gesture, Message msg) {
                apriFiglia(msg);
                return true;
            }
        });
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                return esterno(r.getUrl());
            }
            @Override public void onPageStarted(WebView v, String url, android.graphics.Bitmap f) { v.evaluateJavascript(NATIVA, null); }
            @Override public void onPageCommitVisible(WebView v, String url) { v.evaluateJavascript(NATIVA, null); v.evaluateJavascript(LEGGERA, null); }
            @Override public void onPageFinished(WebView v, String url) { v.evaluateJavascript(LEGGERA, null); }
            @Override public void onReceivedError(WebView v, WebResourceRequest r, WebResourceError e) {
                if (r.isForMainFrame())
                    v.loadData("<html><body style='font-family:sans-serif;padding:24px'><h2>Nessuna connessione</h2>"
                        + "<p>Controlla il Wi-Fi e riprova.</p><button onclick='location.href=\"" + hubUrl() + "\"' style='font-size:18px;padding:12px'>Riprova</button>"
                        + "<p style='color:#888;font-size:13px'>Impostazioni: tieni premuto il tasto Indietro.</p></body></html>", "text/html", "UTF-8");
            }
        });
        web.setDownloadListener(new DownloadListener() {
            public void onDownloadStart(String url, String ua, String cd, String mime, long len) {
                if (url.startsWith("http")) esterno(Uri.parse(url));
            }
        });
        setContentView(web);
        if (b != null) web.restoreState(b); else web.loadUrl(hubUrl());
    }

    /** Il V2 ha una GPU debole: niente sfocature in tempo reale e menu laterale senza animazioni a cascata. */
    private static final String LEGGERA = "(function(){if(document.getElementById('gr-leggera'))return;var s=document.createElement('style');s.id='gr-leggera';"
        + "s.textContent='*,*::before,*::after{-webkit-backdrop-filter:none!important;backdrop-filter:none!important;filter:none!important;"
        + "transition:none!important;box-shadow:none!important;text-shadow:none!important;scroll-behavior:auto!important;}"
        + ".drawer{transition:transform .16s ease-out!important}"
        + ".drawer-overlay{transition:opacity .1s linear!important}"
        + ".drawer .nav-group-header,.drawer .nav-item,.drawer .sidebar-brand>*,.drawer .sidebar-brand img{opacity:1!important;transform:none!important}';"
        + "(document.head||document.documentElement).appendChild(s);})()";

    /** Segna la pagina come "dentro l'app": gli stili solo-app della Hub (html.nativa) si attivano qui e non sul sito. */
    private static final String NATIVA = "try{document.documentElement.classList.add('nativa')}catch(e){}";

    private java.io.File fotoFile;
    private static final int REQ_FOTO = 12;

    /** Scatto con la fotocamera di sistema; il file va in cache e torna alla pagina come se fosse scelto da un input. */
    private void scattaFoto() throws Exception {
        java.io.File dir = new java.io.File(getCacheDir(), "foto");
        dir.mkdirs();
        fotoFile = new java.io.File(dir, "scatto_" + System.currentTimeMillis() + ".jpg");
        Uri out = Uri.parse("content://it.gardenriver.agente.foto/foto/" + fotoFile.getName());
        Intent i = new Intent(android.provider.MediaStore.ACTION_IMAGE_CAPTURE);
        i.putExtra(android.provider.MediaStore.EXTRA_OUTPUT, out);
        i.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_READ_URI_PERMISSION);
        i.setClipData(android.content.ClipData.newRawUri("foto", out));
        startActivityForResult(i, REQ_FOTO);
    }

    private String hubUrl() { return getSharedPreferences("agente", 0).getString("hub_url", "https://gardenhub.it"); }

    private void avviaServizio() {
        Intent s = new Intent(this, PrintService.class);
        if (Build.VERSION.SDK_INT >= 26) startForegroundService(s); else startService(s);
    }

    private void configura(WebView w) {
        WebSettings s = w.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setJavaScriptCanOpenWindowsAutomatically(true);
        s.setSupportMultipleWindows(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(false);
        s.setSaveFormData(false);
        s.setGeolocationEnabled(false);
        s.setSupportZoom(false);
        if (Build.VERSION.SDK_INT >= 26) s.setSafeBrowsingEnabled(false);
        CookieManager.getInstance().setAcceptCookie(true);
    }

    /** true = gestito fuori dalla WebView (link di altri siti, tel:, whatsapp...). */
    private boolean esterno(Uri u) {
        String sch = u.getScheme() == null ? "" : u.getScheme();
        String host = u.getHost() == null ? "" : u.getHost();
        boolean nostro = (sch.equals("https") || sch.equals("http")) && (host.endsWith("gardenhub.it") || host.endsWith("firebaseapp.com")
            || host.endsWith("google.com") || host.endsWith("gstatic.com") || host.endsWith("googleapis.com") || host.equals("localhost"));
        if (nostro || sch.equals("about") || sch.equals("blob") || sch.equals("data") || sch.equals("javascript")) return false;
        try { startActivity(new Intent(Intent.ACTION_VIEW, u)); } catch (ActivityNotFoundException e) { }
        return true;
    }

    /** window.open(): la nuova finestra (anteprime, documenti da stampare) si apre in un pannello a parte. */
    private void apriFiglia(Message msg) {
        webFiglia = new WebView(this);
        configura(webFiglia);
        webFiglia.addJavascriptInterface(new Ponte(), "GRNativo");
        webFiglia.setWebChromeClient(new WebChromeClient() {
            @Override public void onCloseWindow(WebView w) { chiudiFiglia(); }
        });
        webFiglia.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                Uri u = r.getUrl();
                if ("wa.me".equals(u.getHost()) || (u.getScheme() != null && !u.getScheme().startsWith("http") && !u.getScheme().equals("about") && !u.getScheme().equals("blob") && !u.getScheme().equals("data"))) {
                    try { startActivity(new Intent(Intent.ACTION_VIEW, u)); } catch (ActivityNotFoundException e) { }
                    if ("about".equals(v.getUrl())) chiudiFiglia();
                    return true;
                }
                return false;
            }
        });
        figlia = new Dialog(this, android.R.style.Theme_NoTitleBar_Fullscreen);
        figlia.requestWindowFeature(Window.FEATURE_NO_TITLE);
        figlia.setContentView(webFiglia, new ViewGroup.LayoutParams(-1, -1));
        figlia.setOnKeyListener(new android.content.DialogInterface.OnKeyListener() {
            public boolean onKey(android.content.DialogInterface d, int k, KeyEvent e) {
                if (k == KeyEvent.KEYCODE_BACK && e.getAction() == KeyEvent.ACTION_UP) { chiudiFiglia(); return true; }
                return k == KeyEvent.KEYCODE_BACK;
            }
        });
        WebView.WebViewTransport tr = (WebView.WebViewTransport) msg.obj;
        tr.setWebView(webFiglia);
        msg.sendToTarget();
        figlia.show();
    }

    private void chiudiFiglia() {
        if (figlia != null) { figlia.dismiss(); figlia = null; }
        if (webFiglia != null) { webFiglia.destroy(); webFiglia = null; }
    }

    @Override protected void onActivityResult(int req, int res, Intent data) {
        if (req == REQ_FOTO && chooser != null) {
            boolean ok = res == RESULT_OK && fotoFile != null && fotoFile.length() > 0;
            chooser.onReceiveValue(ok ? new Uri[]{Uri.fromFile(fotoFile)} : null);
            chooser = null;
        } else if (req == REQ_FILE && chooser != null) {
            chooser.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(res, data));
            chooser = null;
        } else super.onActivityResult(req, res, data);
    }

    @Override public boolean onKeyDown(int k, KeyEvent e) {
        if (k == KeyEvent.KEYCODE_BACK) { backLungo = false; e.startTracking(); return true; }
        return super.onKeyDown(k, e);
    }
    @Override public boolean onKeyLongPress(int k, KeyEvent e) {
        if (k == KeyEvent.KEYCODE_BACK) { backLungo = true; startActivity(new Intent(this, SettingsActivity.class)); return true; }
        return super.onKeyLongPress(k, e);
    }
    @Override public boolean onKeyUp(int k, KeyEvent e) {
        if (k == KeyEvent.KEYCODE_BACK) {
            if (!backLungo) { if (web.canGoBack()) web.goBack(); else moveTaskToBack(true); }
            return true;
        }
        return super.onKeyUp(k, e);
    }

    @Override protected void onSaveInstanceState(Bundle b) { super.onSaveInstanceState(b); web.saveState(b); }
    @Override protected void onResume() { super.onResume(); web.onResume(); }
    @Override protected void onPause() { super.onPause(); web.onPause(); CookieManager.getInstance().flush(); }

    /** Debug: stampa byte grezzi sulla stampante integrata (adb shell am broadcast -a it.gardenriver.agente.RAW --es hex ...). */
    public static void stampaGrezzo(byte[] dati) throws Exception {
        android.bluetooth.BluetoothAdapter ad = android.bluetooth.BluetoothAdapter.getDefaultAdapter();
        android.bluetooth.BluetoothDevice dev = null;
        for (android.bluetooth.BluetoothDevice d : ad.getBondedDevices()) if (BT_INTERNA.equals(d.getAddress())) { dev = d; break; }
        if (dev == null) throw new Exception("stampante non trovata");
        android.bluetooth.BluetoothSocket sk = dev.createRfcommSocketToServiceRecord(java.util.UUID.fromString("00001101-0000-1000-8000-00805F9B34FB"));
        try { ad.cancelDiscovery(); sk.connect(); sk.getOutputStream().write(dati); sk.getOutputStream().flush(); Thread.sleep(Math.min(8000, 600 + dati.length / 6)); }
        finally { try { sk.close(); } catch (Exception e) { } }
    }

    private static final String BT_INTERNA = "00:11:22:33:44:55";

    /** Invia ESC/POS alla stampante integrata del V2 (dispositivo Bluetooth virtuale gia' associato dal sistema). */
    private void inviaInterna(byte[] dati) throws Exception {
        android.bluetooth.BluetoothAdapter ad = android.bluetooth.BluetoothAdapter.getDefaultAdapter();
        if (ad == null) throw new Exception("Bluetooth non disponibile");
        if (!ad.isEnabled()) ad.enable();
        android.bluetooth.BluetoothDevice dev = null;
        for (android.bluetooth.BluetoothDevice d : ad.getBondedDevices())
            if (BT_INTERNA.equals(d.getAddress())) { dev = d; break; }
        if (dev == null) throw new Exception("stampante integrata non trovata (questo non e' un Sunmi V2?)");
        android.bluetooth.BluetoothSocket sk = dev.createRfcommSocketToServiceRecord(java.util.UUID.fromString("00001101-0000-1000-8000-00805F9B34FB"));
        try {
            ad.cancelDiscovery();
            sk.connect();
            OutputStream o = sk.getOutputStream();
            o.write(dati); o.flush();
            Thread.sleep(Math.min(8000, 600 + dati.length / 6));
        } finally { try { sk.close(); } catch (Exception e) { } }
    }

    /** Ponte JavaScript: la Hub stampa direttamente sulla stampante di rete, senza proxy. */
    public class Ponte {
        /** Notifica Android per un avviso di reparto (stessi eventi di Telegram). */
        @JavascriptInterface public void notifica(String titolo, String testo) {
            android.app.NotificationManager nm = (android.app.NotificationManager) getSystemService(NOTIFICATION_SERVICE);
            if (Build.VERSION.SDK_INT >= 26)
                nm.createNotificationChannel(new android.app.NotificationChannel("avvisi", "Avvisi reparti", android.app.NotificationManager.IMPORTANCE_HIGH));
            android.app.PendingIntent pi = android.app.PendingIntent.getActivity(MainActivity.this, 0, new Intent(MainActivity.this, MainActivity.class),
                Build.VERSION.SDK_INT >= 23 ? android.app.PendingIntent.FLAG_IMMUTABLE : 0);
            android.app.Notification.Builder nb = Build.VERSION.SDK_INT >= 26 ? new android.app.Notification.Builder(MainActivity.this, "avvisi") : new android.app.Notification.Builder(MainActivity.this);
            nb.setContentTitle(titolo).setContentText(testo).setStyle(new android.app.Notification.BigTextStyle().bigText(testo))
              .setSmallIcon(android.R.drawable.ic_popup_reminder).setContentIntent(pi).setAutoCancel(true)
              .setDefaults(android.app.Notification.DEFAULT_ALL).setPriority(android.app.Notification.PRIORITY_HIGH);
            nm.notify((int) (System.currentTimeMillis() & 0x7fffffff), nb.build());
        }
        @JavascriptInterface public String versione() { return "1.1"; }
        @JavascriptInterface public void impostazioni() {
            runOnUiThread(new Runnable() { public void run() { startActivity(new Intent(MainActivity.this, SettingsActivity.class)); } });
        }
        @JavascriptInterface public void stampa(final String id, final String ip, final String xml) {
            new Thread(new Runnable() { public void run() {
                boolean ok = false; String err = "";
                try {
                    if (ip.equals("interna")) {
                        // Stampante integrata V2 (58mm, niente taglierina): dispositivo Bluetooth virtuale, ESC/POS grezzo
                        byte[] dati = EposConverter.converti(xml, 32, 42, 384);
                        byte[] coda = new byte[]{'\n', '\n', '\n'};
                        java.io.ByteArrayOutputStream bo = new java.io.ByteArrayOutputStream();
                        bo.write(dati); bo.write(coda);
                        inviaInterna(bo.toByteArray());
                    } else {
                    if (!ip.matches("\\d{1,3}(\\.\\d{1,3}){3}") || !InetAddress.getByName(ip).isSiteLocalAddress())
                        throw new Exception("IP non di rete locale");
                    byte[] dati = EposConverter.converti(xml);
                    Socket s = new Socket();
                    try {
                        s.connect(new InetSocketAddress(ip, 9100), 5000);
                        OutputStream o = s.getOutputStream();
                        o.write(dati); o.flush();
                    } finally { try { s.close(); } catch (Exception e) { } }
                    }
                    ok = true;
                } catch (Exception e) {
                    err = "stampante " + (ip.equals("interna") ? "integrata" : ip) + ": " + (e.getMessage() == null ? e.toString() : e.getMessage());
                }
                final String js = "window.__grNativoRis&&window.__grNativoRis(" + JSONObject.quote(id) + "," + ok + "," + JSONObject.quote(err) + ")";
                runOnUiThread(new Runnable() { public void run() { if (web != null) web.evaluateJavascript(js, null); } });
            } }).start();
        }
    }
}
