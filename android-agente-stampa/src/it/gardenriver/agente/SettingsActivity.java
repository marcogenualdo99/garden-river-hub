package it.gardenriver.agente;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.text.InputType;
import android.view.View;
import android.widget.*;

public class SettingsActivity extends Activity {
    private EditText url, token;
    private TextView stato;
    private final Handler h = new Handler();
    private final Runnable giro = new Runnable() {
        @Override public void run() {
            SharedPreferences q = getSharedPreferences("agente", 0);
            stato.setText(q.getString("stato", "Fermo") + "\n" + q.getString("feed_stato", "Avvisi: non ancora avviati"));
            h.postDelayed(this, 2000);
        }
    };

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        if (Build.VERSION.SDK_INT >= 33) requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"}, 1);
        final SharedPreferences sp = getSharedPreferences("agente", 0);
        LinearLayout l = new LinearLayout(this);
        l.setOrientation(LinearLayout.VERTICAL);
        l.setPadding(32, 32, 32, 32);
        TextView t = new TextView(this);
        t.setText("Impostazioni Garden Hub (V2)"); t.setTextSize(20);
        l.addView(t);
        url = new EditText(this); url.setHint("URL funzione agente"); url.setSingleLine(true);
        url.setText(sp.getString("url", "https://stampa-agente-113994721180.europe-west1.run.app"));
        l.addView(url);
        final EditText hub = new EditText(this); hub.setHint("Indirizzo Hub"); hub.setSingleLine(true);
        hub.setText(sp.getString("hub_url", "https://gardenhub.it"));
        hub.addTextChangedListener(new android.text.TextWatcher() {
            public void afterTextChanged(android.text.Editable e) { sp.edit().putString("hub_url", e.toString().trim()).apply(); }
            public void beforeTextChanged(CharSequence a, int b, int c, int d) { }
            public void onTextChanged(CharSequence a, int b, int c, int d) { }
        });
        l.addView(hub);
        token = new EditText(this); token.setHint("Token"); token.setSingleLine(true);
        token.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        token.setText(sp.getString("token", ""));
        l.addView(token);
        Button avvia = new Button(this); avvia.setText("Salva e avvia");
        avvia.setOnClickListener(new View.OnClickListener() { public void onClick(View v) {
            sp.edit().putString("url", url.getText().toString().trim())
              .putString("token", token.getText().toString().trim()).putBoolean("attivo", true).apply();
            Intent s = new Intent(SettingsActivity.this, PrintService.class);
            if (Build.VERSION.SDK_INT >= 26) startForegroundService(s); else startService(s);
        }});
        l.addView(avvia);
        Button apri = new Button(this); apri.setText("Torna alla Hub");
        apri.setOnClickListener(new View.OnClickListener() { public void onClick(View v) {
            sp.edit().putString("url", url.getText().toString().trim())
              .putString("token", token.getText().toString().trim()).apply();
            finish();
        }});
        l.addView(apri);
        Button ferma = new Button(this); ferma.setText("Ferma");
        ferma.setOnClickListener(new View.OnClickListener() { public void onClick(View v) {
            sp.edit().putBoolean("attivo", false).apply();
            stopService(new Intent(SettingsActivity.this, PrintService.class));
            sp.edit().putString("stato", "Fermo").apply();
        }});
        l.addView(ferma);
        Button batt = new Button(this); batt.setText("Avvisi con app chiusa: escludi dal risparmio energetico");
        batt.setOnClickListener(new View.OnClickListener() { public void onClick(View v) {
            try {
                if (Build.VERSION.SDK_INT >= 23) startActivity(new Intent(android.provider.Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, android.net.Uri.parse("package:" + getPackageName())));
            } catch (Exception e) { startActivity(new Intent(android.provider.Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)); }
        }});
        l.addView(batt);
        Button rich = new Button(this); rich.setText("Richiedi di nuovo la chiave avvisi");
        rich.setOnClickListener(new View.OnClickListener() { public void onClick(View v) {
            sp.edit().remove("feed_key").remove("feed_since").remove("feed_ids").apply();   // la Hub la ripassa alla prossima pagina aperta
            Toast.makeText(SettingsActivity.this, "Apri una pagina della Hub per riconfigurare gli avvisi", Toast.LENGTH_LONG).show();
        }});
        l.addView(rich);
        stato = new TextView(this); stato.setTextSize(16); stato.setPadding(0, 24, 0, 0);
        l.addView(stato);
        ScrollView sv = new ScrollView(this); sv.addView(l);
        setContentView(sv);
    }
    @Override protected void onResume() { super.onResume(); h.post(giro); }
    @Override protected void onPause() { super.onPause(); h.removeCallbacks(giro); }
}
