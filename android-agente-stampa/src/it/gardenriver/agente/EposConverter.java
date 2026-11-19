package it.gardenriver.agente;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.NodeList;
import android.util.Base64;

/** Traduce l'XML Epson ePOS-Print generato dalla Hub in ESC/POS (stessa logica di proxy_stampante.py). */
public class EposConverter {
    static final int COLS_A = 48, COLS_B = 64;

    private static String nome(Element e) {
        String t = e.getTagName();
        int i = t.lastIndexOf(':');
        return i >= 0 ? t.substring(i + 1) : t;
    }

    /** Riduce gli spazi fra colonne (nome ... prezzo) finche' la riga entra; false se non basta. */
    static String stringi(String part, int target) {
        while (part.length() > target) {
            int best = -1, bestLen = 1, i = 0;
            String core = part.replaceFirst("^ +", "");
            int off = part.length() - core.length();
            for (i = off; i < part.length(); ) {
                if (part.charAt(i) == ' ') {
                    int j = i; while (j < part.length() && part.charAt(j) == ' ') j++;
                    if (j - i > bestLen && j < part.length()) { best = i; bestLen = j - i; }
                    i = j;
                } else i++;
            }
            if (best < 0) break;
            int excess = part.length() - target;
            int togli = Math.min(excess, bestLen - 1);
            part = part.substring(0, best) + part.substring(best + togli);
        }
        return part;
    }

    private static boolean bool(String v) { return "true".equalsIgnoreCase(v); }

    private static int num(String v, int def) {
        try { return Integer.parseInt(v.trim()); } catch (Exception e) { return def; }
    }

    public static byte[] converti(String xml) throws Exception { return converti(xml, COLS_A, COLS_B, 0); }

    /** colsA/colsB: colonne a tutta larghezza (80mm: 48/64, 58mm: 32/42). maxPx>0: ridimensiona le immagini (58mm: 384). */
    public static byte[] converti(String xml, int colsA, int colsB, int maxPx) throws Exception {
        Document doc = DocumentBuilderFactory.newInstance().newDocumentBuilder()
            .parse(new ByteArrayInputStream(xml.getBytes("UTF-8")));
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        out.write(new byte[]{0x1b, '@'});
        String align = "left", font = "font_a";
        boolean em = false, reverse = false;
        int w = 1, h = 1, lineLen = 0, lineEw = 1;
        NodeList all = doc.getElementsByTagName("*");
        for (int k = 0; k < all.getLength(); k++) {
            Element el = (Element) all.item(k);
            String t = nome(el);
            if (t.equals("text")) {
                String txt = el.getTextContent().replace("\r", "");
                boolean hasRev = el.hasAttribute("reverse");
                if (reverse && hasRev && !bool(el.getAttribute("reverse")) && txt.startsWith("\n")) {
                    int fc = font.equals("font_b") ? colsB : colsA;
                    if (maxPx > 0) {
                        // spazi alla larghezza corrente per coprire il resto della riga (misurato in colonne 1x)
                        int resto = fc - lineLen * lineEw;
                        for (int i = 0; i < resto / w; i++) out.write(' ');
                    } else {
                        int cols = fc / w;
                        if (lineLen > 0 && lineLen < cols)
                            for (int i = 0; i < cols - lineLen; i++) out.write(' ');
                    }
                }
                if (el.hasAttribute("align") && !el.getAttribute("align").equals(align)) {
                    align = el.getAttribute("align");
                    out.write(new byte[]{0x1b, 'a', (byte) (align.equals("center") ? 1 : align.equals("right") ? 2 : 0)});
                }
                if (el.hasAttribute("font") && !el.getAttribute("font").equals(font)) {
                    font = el.getAttribute("font");
                    out.write(new byte[]{0x1b, 'M', (byte) (font.equals("font_b") ? 1 : 0)});
                }
                if (el.hasAttribute("em") && bool(el.getAttribute("em")) != em) {
                    em = bool(el.getAttribute("em"));
                    out.write(new byte[]{0x1b, 'E', (byte) (em ? 1 : 0)});
                }
                if (hasRev && bool(el.getAttribute("reverse")) != reverse) {
                    reverse = bool(el.getAttribute("reverse"));
                    out.write(new byte[]{0x1d, 'B', (byte) (reverse ? 1 : 0)});
                }
                if (el.hasAttribute("width") || el.hasAttribute("height")) {
                    w = Math.max(1, Math.min(8, el.hasAttribute("width") ? num(el.getAttribute("width"), w) : w));
                    h = Math.max(1, Math.min(8, el.hasAttribute("height") ? num(el.getAttribute("height"), h) : h));
                    out.write(new byte[]{0x1d, '!', (byte) (((w - 1) << 4) | (h - 1))});
                }
                if (maxPx > 0) {
                    // Carta stretta (58mm): niente righe spezzate a meta' parola.
                    // Se una riga a doppia larghezza non entra, prova a larghezza normale; poi va a capo sugli spazi.
                    int fcols = font.equals("font_b") ? colsB : colsA;
                    String[] parti = txt.split("\n", -1);
                    for (int pi = 0; pi < parti.length; pi++) {
                        if (pi > 0) { out.write('\n'); lineLen = 0; lineEw = w; }
                        String part = parti[pi];
                        if (reverse && lineLen == 0 && part.trim().length() > 0) {
                            // Banda nera: la Hub la riempie per 80mm. La rifaccio a larghezza piena della carta 58mm.
                            String core = part.trim();
                            int lead = part.length() - part.replaceFirst("^ +", "").length();
                            int e = w;
                            if (core.length() + 2 > fcols / e && e > 1) e = 1;
                            int L = fcols / e;
                            if (core.length() + 2 <= L) {
                                String inner = " " + core + " ";
                                int lp = lead >= 2 ? (L - inner.length()) / 2 : 0;
                                StringBuilder sb2 = new StringBuilder();
                                for (int i = 0; i < lp; i++) sb2.append(' ');
                                sb2.append(inner);
                                while (sb2.length() < L) sb2.append(' ');
                                if (e != w) out.write(new byte[]{0x1d, '!', (byte) (h - 1)});
                                out.write(sb2.toString().getBytes("UTF-8"));
                                if (e != w) out.write(new byte[]{0x1d, '!', (byte) (((w - 1) << 4) | (h - 1))});
                                lineLen = L; lineEw = e;
                                continue;
                            }
                        }
                        int ew = w, lim = fcols / ew;
                        if (!reverse) {
                            // riga di soli simboli uguali (=====, -----): taglia alla larghezza della carta
                            if (part.length() > fcols && part.matches("(.)\\1+")) part = part.substring(0, fcols / (lineLen == 0 ? ew : 1));
                            else if (lineLen + part.length() > lim) { String sq = stringi(part, lim - lineLen); if (lineLen + sq.length() <= lim) part = sq; }
                        }
                        if (ew > 1 && lineLen + part.length() > lim) {
                            ew = 1; lim = fcols;
                            if (!reverse) part = stringi(part, lim - lineLen);
                            out.write(new byte[]{0x1d, '!', (byte) (h - 1)});
                        }
                        if (lineLen == 0) lineEw = ew;
                        while (lineLen + part.length() > lim) {
                            int room = lim - lineLen;
                            if (room <= 0) {
                                out.write('\n'); lineLen = 0; lineEw = ew;
                                part = part.replaceFirst("^ +", "");
                                continue;
                            }
                            int cut = part.lastIndexOf(' ', room);
                            if (cut <= 0) cut = room;
                            out.write(part.substring(0, cut).replaceFirst(" +$", "").getBytes("UTF-8"));
                            out.write('\n'); lineLen = 0; lineEw = ew;
                            part = part.substring(cut).replaceFirst("^ +", "");
                        }
                        out.write(part.getBytes("UTF-8"));
                        lineLen += part.length();
                        if (ew != w) out.write(new byte[]{0x1d, '!', (byte) (((w - 1) << 4) | (h - 1))});
                    }
                } else {
                out.write(txt.getBytes("UTF-8"));
                int nl = txt.lastIndexOf('\n');
                lineLen = nl >= 0 ? txt.length() - nl - 1 : lineLen + txt.length();
                }
            } else if (t.equals("feed")) {
                int n = Math.max(1, num(el.getAttribute("line"), 1));
                for (int i = 0; i < n; i++) out.write('\n');
                lineLen = 0; lineEw = w;
            } else if (t.equals("image")) {
                int iw = num(el.getAttribute("width"), 0), ih = num(el.getAttribute("height"), 0);
                byte[] data = Base64.decode(el.getTextContent().trim(), Base64.DEFAULT);
                int rb = (iw + 7) / 8;
                if (maxPx > 0 && iw > maxPx && ih > 0 && iw > 0) {
                    // riduzione a vicino piu' prossimo del raster 1 bit (MSB a sinistra)
                    int nw = maxPx / 8 * 8, nh = Math.max(1, ih * nw / iw), nrb = nw / 8;
                    byte[] n = new byte[nrb * nh];
                    for (int y = 0; y < nh; y++) {
                        int sy = Math.min(ih - 1, y * ih / nh);
                        for (int x = 0; x < nw; x++) {
                            int sx = x * iw / nw, idx = sy * rb + (sx >> 3);
                            if (idx < data.length && (data[idx] & (0x80 >> (sx & 7))) != 0) n[y * nrb + (x >> 3)] |= (byte) (0x80 >> (x & 7));
                        }
                    }
                    iw = nw; ih = nh; rb = nrb; data = n;
                }
                int len = Math.min(data.length, rb * ih);
                out.write(new byte[]{0x1d, 'v', '0', 0, (byte) (rb & 255), (byte) (rb >> 8), (byte) (ih & 255), (byte) (ih >> 8)});
                out.write(data, 0, len);
            } else if (t.equals("cut")) {
                out.write(new byte[]{0x1d, 'V', 'B', 0});
            }
        }
        return out.toByteArray();
    }
}
