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
        int w = 1, h = 1, lineLen = 0;
        NodeList all = doc.getElementsByTagName("*");
        for (int k = 0; k < all.getLength(); k++) {
            Element el = (Element) all.item(k);
            String t = nome(el);
            if (t.equals("text")) {
                String txt = el.getTextContent().replace("\r", "");
                boolean hasRev = el.hasAttribute("reverse");
                if (reverse && hasRev && !bool(el.getAttribute("reverse")) && txt.startsWith("\n")) {
                    int cols = (font.equals("font_b") ? colsB : colsA) / w;
                    if (lineLen > 0 && lineLen < cols)
                        for (int i = 0; i < cols - lineLen; i++) out.write(' ');
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
                out.write(txt.getBytes("UTF-8"));
                int nl = txt.lastIndexOf('\n');
                lineLen = nl >= 0 ? txt.length() - nl - 1 : lineLen + txt.length();
            } else if (t.equals("feed")) {
                int n = Math.max(1, num(el.getAttribute("line"), 1));
                for (int i = 0; i < n; i++) out.write('\n');
                lineLen = 0;
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
