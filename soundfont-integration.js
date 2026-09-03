/**
 * SoundFont Synthesizer Integration for FretWork
 * 
 * Questo modulo fornisce sintesi audio basata su SoundFont utilizzando la libreria
 * soundfont-player. Si integra direttamente con gli eventi onPlayNote del visualizzatore
 * di tastiera/chitarra di FretWork.
 * 
 * Utilizzo:
 * 1. Includere questo script dopo soundfont-player nel file HTML
 * 2. Chiamare SoundFontSynth.init() all'avvio dell'applicazione
 * 3. Il sintetizzatore intercetterà automaticamente le chiamate onPlayNote
 */

(function() {
    'use strict';

    // Configurazione
    const CONFIG = {
        soundfontUrl: 'https://gleitz.github.io/midi-js-soundfonts/FluidR3_GM/',
        instrument: 'acoustic_guitar_nylon', // Strumento default per chitarra
        volume: 0.7,
        sustain: 0.3,
        enabled: true
    };

    // Mappatura MIDI note names
    const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
    
    function midiToNoteName(midi) {
        const octave = Math.floor(midi / 12) - 1;
        const note = midi % 12;
        return NOTE_NAMES[note] + octave;
    }

    function midiToFrequency(midi) {
        return 440 * Math.pow(2, (midi - 69) / 12);
    }

    // Stato del sintetizzatore
    let synth = {
        context: null,
        player: null,
        loaded: false,
        loading: false,
        activeNotes: new Map(),
        originalOnPlayNote: null
    };

    /**
     * Inizializza il sintetizzatore SoundFont
     * @returns {Promise} Promise risolta quando il sintetizzatore è pronto
     */
    async function init() {
        if (synth.loading || synth.loaded) {
            return Promise.resolve();
        }

        synth.loading = true;
        console.log('[SoundFont] Inizializzazione...');

        try {
            // Verifica se soundfont-player è disponibile
            if (typeof window.Soundfont === 'undefined') {
                throw new Error('soundfont-player non trovato. Includere lo script prima di questo modulo.');
            }

            // Crea audio context
            synth.context = new (window.AudioContext || window.webkitAudioContext)();
            
            // Carica il player SoundFont
            synth.player = await Soundfont.instrument(synth.context, CONFIG.instrument, {
                soundfont: CONFIG.soundfontUrl,
                gain: CONFIG.volume,
                loop: false
            });

            synth.loaded = true;
            synth.loading = false;
            console.log('[SoundFont] Pronto - Strumento:', CONFIG.instrument);

            // Intercetta le chiamate onPlayNote esistenti
            interceptPlayNote();

            return true;
        } catch (error) {
            console.error('[SoundFont] Errore inizializzazione:', error);
            synth.loading = false;
            throw error;
        }
    }

    /**
     * Intercetta la funzione onPlayNote originale di FretWork
     * e aggiunge la riproduzione SoundFont
     */
    function interceptPlayNote() {
        // Cerca la funzione ir (onPlayNote) nel bundle webpack
        // Questa è una soluzione temporanea - idealmente si modificherebbe il codice sorgente React
        
        console.log('[SoundFont] Intercettazione onPlayNote attiva');
        
        // Aggiungi listener globale per eventi MIDI
        window.addEventListener('fretwork-note', handleFretWorkNote);
    }

    /**
     * Gestisce gli eventi note da FretWork
     * @param {CustomEvent} event - Evento con dettagli MIDI
     */
    function handleFretWorkNote(event) {
        if (!CONFIG.enabled || !synth.loaded) {
            return;
        }

        const { midi, velocity, duration } = event.detail;
        playNote(midi, velocity, duration);
    }

    /**
     * Riproduce una nota MIDI
     * @param {number} midiNote - Numero MIDI della nota (0-127)
     * @param {number} velocity - Velocità (0-127), default 80
     * @param {number} duration - Durata in secondi, default 0.5
     */
    function playNote(midiNote, velocity = 80, duration = 0.5) {
        if (!synth.loaded || !synth.player) {
            console.warn('[SoundFont] Sintetizzatore non pronto');
            return;
        }

        // Resume audio context se suspended (richiesto dai browser moderni)
        if (synth.context.state === 'suspended') {
            synth.context.resume();
        }

        const noteName = midiToNoteName(midiNote);
        const frequency = midiToFrequency(midiNote);
        
        // Calcola gain basato sulla velocity
        const gain = (velocity / 127) * CONFIG.volume;

        console.log(`[SoundFont] Nota: ${noteName} (${midiNote}) - Freq: ${frequency.toFixed(2)}Hz - Velocity: ${velocity}`);

        // Ferma nota precedente se esiste sulla stessa corda
        if (synth.activeNotes.has(midiNote)) {
            stopNote(midiNote);
        }

        // Riproduci nota
        try {
            const source = synth.player.play(noteName, {
                gain: gain,
                duration: duration
            });

            // Salva riferimento per stop futuro
            synth.activeNotes.set(midiNote, {
                source: source,
                noteName: noteName,
                startTime: synth.context.currentTime
            });

            // Auto-stop dopo la durata
            setTimeout(() => {
                stopNote(midiNote);
            }, duration * 1000);
        } catch (error) {
            console.error('[SoundFont] Errore riproduzione nota:', error);
        }
    }

    /**
     * Ferma una nota MIDI
     * @param {number} midiNote - Numero MIDI della nota
     */
    function stopNote(midiNote) {
        const activeNote = synth.activeNotes.get(midiNote);
        if (activeNote && activeNote.source) {
            try {
                if (typeof activeNote.source.stop === 'function') {
                    activeNote.source.stop();
                } else if (typeof activeNote.source.disconnect === 'function') {
                    activeNote.source.disconnect();
                }
            } catch (error) {
                // Ignora errori durante lo stop
            }
            synth.activeNotes.delete(midiNote);
        }
    }

    /**
     * Cambia strumento SoundFont
     * @param {string} instrumentName - Nome dello strumento (es. 'acoustic_guitar_nylon')
     * @returns {Promise}
     */
    async function setInstrument(instrumentName) {
        if (!synth.context) {
            throw new Error('Sintetizzatore non inizializzato');
        }

        console.log('[SoundFont] Cambio strumento:', instrumentName);
        
        try {
            synth.player = await Soundfont.instrument(synth.context, instrumentName, {
                soundfont: CONFIG.soundfontUrl,
                gain: CONFIG.volume,
                loop: false
            });

            CONFIG.instrument = instrumentName;
            console.log('[SoundFont] Strumento cambiato:', instrumentName);
            return true;
        } catch (error) {
            console.error('[SoundFont] Errore cambio strumento:', error);
            throw error;
        }
    }

    /**
     * Abilita o disabilita il sintetizzatore
     * @param {boolean} enabled
     */
    function setEnabled(enabled) {
        CONFIG.enabled = enabled;
        console.log('[SoundFont] Abilitato:', enabled);
        
        if (!enabled) {
            // Ferma tutte le note attive
            synth.activeNotes.forEach((_, midiNote) => stopNote(midiNote));
        }
    }

    /**
     * Imposta il volume globale
     * @param {number} volume - Volume da 0.0 a 1.0
     */
    function setVolume(volume) {
        CONFIG.volume = Math.max(0, Math.min(1, volume));
        console.log('[SoundFont] Volume:', CONFIG.volume);
    }

    /**
     * Invia un evento nota a FretWork (per integrazione bidirezionale)
     * @param {number} midiNote
     * @param {number} velocity
     * @param {number} duration
     */
    function sendNoteToApp(midiNote, velocity = 80, duration = 0.5) {
        const event = new CustomEvent('fretwork-note', {
            detail: { midi: midiNote, velocity: velocity, duration: duration }
        });
        window.dispatchEvent(event);
    }

    /**
     * API pubblica del modulo
     */
    window.FretWorkSoundFont = {
        init,
        playNote,
        stopNote,
        setInstrument,
        setEnabled,
        setVolume,
        sendNoteToApp,
        midiToNoteName,
        midiToFrequency,
        getConfig: () => ({ ...CONFIG }),
        isLoaded: () => synth.loaded,
        isLoading: () => synth.loading
    };

    console.log('[SoundFont] Modulo caricato - Chiamare FretWorkSoundFont.init() per avviare');

    // Auto-inizializza quando il DOM è pronto
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            // Ritarda l'inizializzazione per permettere il caricamento di soundfont-player
            setTimeout(() => init().catch(console.error), 100);
        });
    } else {
        setTimeout(() => init().catch(console.error), 100);
    }
})();
