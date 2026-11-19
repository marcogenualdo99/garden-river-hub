#!/bin/bash
# Compila l'APK senza Gradle (solo strumenti SDK + JDK). Output: build/GardenHub.apk
set -e
cd "$(dirname "$0")"
TC="$HOME/android-toolchain"
export JAVA_HOME=$(ls -d "$TC"/jdk/*/Contents/Home)
BT="$TC/sdk/build-tools/34.0.0"; AJ="$TC/sdk/platforms/android-34/android.jar"
rm -rf build && mkdir -p build/classes build/gen
mkdir -p build/res && "$BT/aapt2" compile --dir res -o build/res.zip
"$BT/aapt2" link -o build/base.apk build/res.zip -I "$AJ" --manifest AndroidManifest.xml --java build/gen --min-sdk-version 24 --target-sdk-version 33
"$JAVA_HOME/bin/javac" -source 8 -target 8 -Xlint:-options -cp "$AJ" -d build/classes $(find src build/gen -name '*.java')
"$BT/d8" --min-api 24 --lib "$AJ" --output build $(find build/classes -name '*.class')
cp build/base.apk build/unsigned.apk
(cd build && zip -q unsigned.apk classes.dex)
"$BT/zipalign" -f 4 build/unsigned.apk build/aligned.apk
KS="$TC/agente-stampa.keystore"
[ -f "$KS" ] || "$JAVA_HOME/bin/keytool" -genkeypair -keystore "$KS" -storepass gardenriver -keypass gardenriver -alias agente -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Garden River Agente Stampa"
"$BT/apksigner" sign --ks "$KS" --ks-pass pass:gardenriver --key-pass pass:gardenriver --out build/GardenHub.apk build/aligned.apk
echo "OK: $(pwd)/build/GardenHub.apk"
