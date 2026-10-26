package com.example.u_3dgarage

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import android.media.MediaScannerConnection
import android.content.ContentValues
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import java.io.File
import java.io.OutputStream

class MainActivity : FlutterActivity() {
    private val CHANNEL = "com.example.araba_app101/gallery"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL).setMethodCallHandler { call, result ->
            if (call.method == "scanFile") {
                val path = call.argument<String>("path")
                if (path != null) {
                    val file = File(path)
                    MediaScannerConnection.scanFile(
                        context,
                        arrayOf(file.absolutePath),
                        null
                    ) { _, _ -> }
                    result.success(true)
                } else {
                    result.error("INVALID_PATH", "Path is null", null)
                }
            } else if (call.method == "saveImageToGallery") {
                val imageBytes = call.argument<ByteArray>("imageBytes")
                val fileName = call.argument<String>("fileName") ?: "3dgarage_${System.currentTimeMillis()}.jpg"
                if (imageBytes != null) {
                    try {
                        val resolver = context.contentResolver
                        val contentValues = ContentValues().apply {
                            put(MediaStore.Images.Media.DISPLAY_NAME, fileName)
                            put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg")
                            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                                put(MediaStore.Images.Media.RELATIVE_PATH, "Pictures/3DGarage")
                                put(MediaStore.Images.Media.IS_PENDING, 1)
                            }
                        }

                        val imageUri = resolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, contentValues)
                        if (imageUri != null) {
                            val outputStream: OutputStream? = resolver.openOutputStream(imageUri)
                            if (outputStream != null) {
                                outputStream.write(imageBytes)
                                outputStream.close()
                                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                                    contentValues.clear()
                                    contentValues.put(MediaStore.Images.Media.IS_PENDING, 0)
                                    resolver.update(imageUri, contentValues, null, null)
                                }
                                result.success(imageUri.toString())
                            } else {
                                result.error("WRITE_ERROR", "Failed to open output stream", null)
                            }
                        } else {
                            result.error("INSERT_ERROR", "Failed to insert MediaStore entry", null)
                        }
                    } catch (e: Exception) {
                        result.error("SAVE_FAILED", e.localizedMessage, null)
                    }
                } else {
                    result.error("INVALID_BYTES", "Image bytes are null", null)
                }
            } else {
                result.notImplemented()
            }
        }
    }
}
