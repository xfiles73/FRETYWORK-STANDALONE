#!/usr/bin/env python3
"""
Sintetizzatore Audio basato su SoundFont (SF2/SF3)
Utilizza FluidSynth per la sintesi di strumenti musicali MIDI

Questo modulo permette di:
- Caricare file SoundFont (.sf2, .sf3)
- Riprodurre note MIDI con diversi strumenti
- Creare sequenze musicali
- Esportare audio in formato WAV
"""

import os
import time
import threading
from typing import Optional, List, Dict, Tuple
import numpy as np

try:
    import fluidsynth
    FLUIDSYNTH_AVAILABLE = True
except ImportError:
    FLUIDSYNTH_AVAILABLE = False
    print("Warning: pyfluidsynth non disponibile. Installare con: pip install pyfluidsynth")

# Costanti MIDI
NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
MIDI_A4 = 69  # La4 = 440 Hz
DEFAULT_SAMPLE_RATE = 44100


class SoundFontSynth:
    """
    Sintetizzatore basato su SoundFont che utilizza FluidSynth
    
    Attributes:
        sample_rate: Frequenza di campionamento (default: 44100 Hz)
        soundfont_path: Percorso del file SoundFont (.sf2 o .sf3)
    """
    
    def __init__(self, 
                 sample_rate: int = DEFAULT_SAMPLE_RATE,
                 soundfont_path: Optional[str] = None):
        """
        Inizializza il sintetizzatore
        
        Args:
            sample_rate: Frequenza di campionamento in Hz
            soundfont_path: Percorso opzionale al file SoundFont
        """
        if not FLUIDSYNTH_AVAILABLE:
            raise ImportError("pyfluidsynth non è disponibile")
        
        self.sample_rate = sample_rate
        self.soundfont_path = soundfont_path
        self._fs = None
        self._audio_driver = None
        self._initialized = False
        self._lock = threading.Lock()
        
        # Parametri MIDI di default
        self.bank = 0
        self.preset = 0  # Piano di default
        self.volume = 100
        self.reverb = 50
        self.chorus = 50
        
        if soundfont_path:
            self.load_soundfont(soundfont_path)
    
    def _ensure_initialized(self):
        """Assicura che FluidSynth sia inizializzato"""
        if not self._initialized:
            self._initialize()
    
    def _initialize(self):
        """Inizializza l'istanza FluidSynth"""
        with self._lock:
            if self._initialized:
                return
            
            try:
                # Inizializza il sintetizzatore
                self._fs = fluidsynth.Synth(samplerate=self.sample_rate)
                
                # Seleziona il driver audio appropriato
                drivers = fluidsynth.default_audio_driver()
                if drivers:
                    self._audio_driver = fluidsynth.AudioDriver(self._fs, drivers[0])
                
                self._initialized = True
            except Exception as e:
                raise RuntimeError(f"Errore nell'inizializzazione di FluidSynth: {e}")
    
    def load_soundfont(self, soundfont_path: str) -> bool:
        """
        Carica un file SoundFont
        
        Args:
            soundfont_path: Percorso al file .sf2 o .sf3
            
        Returns:
            True se caricato con successo, False altrimenti
        """
        self._ensure_initialized()
        
        if not os.path.exists(soundfont_path):
            raise FileNotFoundError(f"SoundFont non trovato: {soundfont_path}")
        
        with self._lock:
            sfid = self._fs.sfload(soundfont_path)
            if sfid is None or sfid == -1:
                raise RuntimeError(f"Impossibile caricare SoundFont: {soundfont_path}")
            
            self.soundfont_path = soundfont_path
            # Imposta il preset di default
            self._fs.program_select(0, sfid, self.bank, self.preset)
            
        return True
    
    def set_preset(self, bank: int, preset: int):
        """
        Cambia lo strumento (preset)
        
        Args:
            bank: Numero del banco (0-16383)
            preset: Numero del preset (0-127)
        """
        self._ensure_initialized()
        
        if self.soundfont_path is None:
            raise RuntimeError("Nessun SoundFont caricato")
        
        with self._lock:
            sfid = self._fs.get_sfid(0)
            if sfid is not None:
                self._fs.program_select(0, sfid, bank, preset)
                self.bank = bank
                self.preset = preset
    
    def get_available_presets(self) -> List[Dict]:
        """
        Ottiene la lista dei preset disponibili nel SoundFont caricato
        
        Returns:
            Lista di dizionari con informazioni sui preset
        """
        self._ensure_initialized()
        
        presets = []
        if self.soundfont_path and self._fs:
            sfid = self._fs.get_sfid(0)
            if sfid is not None:
                for bank in range(128):
                    for preset_num in range(128):
                        preset_name = self._fs.get_preset_name(sfid, bank, preset_num)
                        if preset_name:
                            presets.append({
                                'bank': bank,
                                'preset': preset_num,
                                'name': preset_name
                            })
        return presets
    
    def note_on(self, note: int, velocity: int = 100, channel: int = 0):
        """
        Attiva una nota MIDI
        
        Args:
            note: Numero della nota MIDI (0-127)
            velocity: Velocità/forza (0-127)
            channel: Canale MIDI (0-15)
        """
        self._ensure_initialized()
        
        with self._lock:
            self._fs.noteon(channel, note, velocity)
    
    def note_off(self, note: int, channel: int = 0):
        """
        Disattiva una nota MIDI
        
        Args:
            note: Numero della nota MIDI (0-127)
            channel: Canale MIDI (0-15)
        """
        self._ensure_initialized()
        
        with self._lock:
            self._fs.noteoff(channel, note)
    
    def play_note(self, note: int, duration: float, velocity: int = 100, channel: int = 0):
        """
        Suona una nota per una durata specifica
        
        Args:
            note: Numero della nota MIDI (0-127)
            duration: Durata in secondi
            velocity: Velocità/forza (0-127)
            channel: Canale MIDI (0-15)
        """
        self.note_on(note, velocity, channel)
        time.sleep(duration)
        self.note_off(note, channel)
    
    def midi_to_frequency(self, midi_note: int) -> float:
        """
        Converte un numero MIDI in frequenza Hz
        
        Args:
            midi_note: Numero della nota MIDI
            
        Returns:
            Frequenza in Hz
        """
        return 440.0 * (2.0 ** ((midi_note - MIDI_A4) / 12.0))
    
    def frequency_to_midi(self, frequency: float) -> int:
        """
        Converte una frequenza in numero MIDI
        
        Args:
            frequency: Frequenza in Hz
            
        Returns:
            Numero della nota MIDI più vicino
        """
        return round(MIDI_A4 + 12 * np.log2(frequency / 440.0))
    
    def get_note_name(self, midi_note: int) -> str:
        """
        Ottiene il nome di una nota MIDI
        
        Args:
            midi_note: Numero della nota MIDI
            
        Returns:
            Nome della nota (es. "C4", "A#3")
        """
        octave = (midi_note // 12) - 1
        note_name = NOTE_NAMES[midi_note % 12]
        return f"{note_name}{octave}"
    
    def set_control(self, control: int, value: int, channel: int = 0):
        """
        Imposta un controllo MIDI (CC)
        
        Args:
            control: Numero del controllo (0-127)
            value: Valore (0-127)
            channel: Canale MIDI (0-15)
        """
        self._ensure_initialized()
        
        with self._lock:
            self._fs.cc(channel, control, value)
    
    def set_reverb(self, level: float):
        """
        Imposta il livello di riverbero
        
        Args:
            level: Livello di riverbero (0.0-1.0)
        """
        self._ensure_initialized()
        
        with self._lock:
            self._fs.set_reverb(level)
            self.reverb = int(level * 100)
    
    def set_chorus(self, level: float):
        """
        Imposta il livello di chorus
        
        Args:
            level: Livello di chorus (0.0-1.0)
        """
        self._ensure_initialized()
        
        with self._lock:
            self._fs.set_chorus(level)
            self.chorus = int(level * 100)
    
    def render_notes(self, notes: List[Tuple[int, float, float]], 
                     duration: float = None) -> np.ndarray:
        """
        Renderizza una sequenza di note in un array numpy
        
        Args:
            notes: Lista di tuple (nota_midi, start_time, duration)
            duration: Durata totale opzionale
            
        Returns:
            Array numpy con l'audio renderizzato
        """
        self._ensure_initialized()
        
        if not notes:
            return np.array([], dtype=np.float32)
        
        # Calcola la durata totale se non specificata
        if duration is None:
            duration = max(start + dur for _, start, dur in notes)
        
        # Crea buffer audio
        num_samples = int(duration * self.sample_rate)
        audio_buffer = np.zeros(num_samples, dtype=np.float32)
        
        # Nota: Questa è una implementazione semplificata
        # Per una renderizzazione completa, si dovrebbe usare
        # fluidsynth direttamente per ottenere i campioni
        
        return audio_buffer
    
    def save_audio(self, output_path: str, notes: List[Tuple[int, float, float]],
                   duration: float = None):
        """
        Salva una sequenza di note come file WAV
        
        Args:
            output_path: Percorso del file di output
            notes: Lista di tuple (nota_midi, start_time, duration)
            duration: Durata totale opzionale
        """
        import wave
        import struct
        
        audio_data = self.render_notes(notes, duration)
        
        if len(audio_data) == 0:
            raise ValueError("Nessun dato audio da salvare")
        
        # Converti in formato PCM a 16 bit
        audio_int16 = (audio_data * 32767).astype(np.int16)
        
        # Scrivi file WAV
        with wave.open(output_path, 'w') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_int16.tobytes())
    
    def close(self):
        """Chiude il sintetizzatore e libera le risorse"""
        with self._lock:
            if self._audio_driver:
                self._audio_driver.delete()
                self._audio_driver = None
            
            if self._fs:
                self._fs.delete()
                self._fs = None
            
            self._initialized = False
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
    
    def __del__(self):
        """Distruttore"""
        try:
            self.close()
        except:
            pass


def find_default_soundfont() -> Optional[str]:
    """
    Cerca un file SoundFont di default nel sistema
    
    Returns:
        Percorso al primo SoundFont trovato, o None
    """
    # Percorsi comuni per SoundFont su Linux
    common_paths = [
        '/usr/share/sounds/sf2/FluidR3_GM.sf2',
        '/usr/share/sounds/sf2/TimGM6mb.sf2',
        '/usr/share/sounds/sf3/default-GM.sf3',
        '/usr/local/share/sounds/sf2/FluidR3_GM.sf2',
        '/usr/share/soundfonts/FluidR3_GM.sf2',
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            return path
    
    # Cerca nella directory corrente
    current_dir = os.getcwd()
    for filename in os.listdir(current_dir):
        if filename.endswith(('.sf2', '.sf3')):
            return os.path.join(current_dir, filename)
    
    return None


def demo():
    """Dimostrazione delle funzionalità del sintetizzatore"""
    print("=" * 60)
    print("DEMO: Sintetizzatore SoundFont")
    print("=" * 60)
    
    if not FLUIDSYNTH_AVAILABLE:
        print("ERRORE: pyfluidsynth non è disponibile")
        print("Installare con: pip install pyfluidsynth")
        return
    
    # Trova un SoundFont
    soundfont = find_default_soundfont()
    
    if not soundfont:
        print("\nNessun SoundFont trovato nel sistema.")
        print("Scaricare un SoundFont (es. FluidR3_GM.sf2) e specificare il percorso.")
        print("\nPercorsi cercati:")
        print("  - /usr/share/sounds/sf2/FluidR3_GM.sf2")
        print("  - /usr/share/sounds/sf2/TimGM6mb.sf2")
        print("  - *.sf2, *.sf3 nella directory corrente")
        return
    
    print(f"\nSoundFont trovato: {soundfont}")
    
    # Crea il sintetizzatore
    synth = SoundFontSynth(soundfont_path=soundfont)
    
    try:
        # Mostra alcuni preset disponibili
        print("\nAlcuni strumenti disponibili:")
        presets = synth.get_available_presets()[:10]
        for p in presets:
            print(f"  Banco {p['bank']:3d}, Preset {p['preset']:3d}: {p['name']}")
        
        # Suona una scala maggiore
        print("\nSuonando una scala di Do maggiore...")
        scale = [60, 62, 64, 65, 67, 69, 71, 72]  # C4 a C5
        
        for note in scale:
            note_name = synth.get_note_name(note)
            freq = synth.midi_to_frequency(note)
            print(f"  Nota: {note_name} (MIDI: {note}, Freq: {freq:.2f} Hz)")
            synth.play_note(note, duration=0.5, velocity=80)
        
        # Suona un accordo
        print("\nSuonando un accordo di Do maggiore...")
        chord = [60, 64, 67]  # C, E, G
        
        for note in chord:
            synth.note_on(note, velocity=70)
        
        time.sleep(1.5)
        
        for note in chord:
            synth.note_off(note)
        
        print("\nDemo completata!")
        
    finally:
        synth.close()


if __name__ == "__main__":
    demo()
