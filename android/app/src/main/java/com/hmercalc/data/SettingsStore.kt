package com.hmercalc.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

// 顶层扩展：DataStore 单例（文件名 settings）。
private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "settings")

@Singleton
class SettingsStore @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    companion object {
        private val KEY_BASE_URL = stringPreferencesKey("base_url")
        const val DEFAULT_BASE_URL = "http://10.0.2.2:8000"
    }

    val baseUrlFlow: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[KEY_BASE_URL] ?: DEFAULT_BASE_URL
    }

    suspend fun setBaseUrl(url: String) {
        context.dataStore.edit { prefs ->
            prefs[KEY_BASE_URL] = url.trim()
        }
    }
}
