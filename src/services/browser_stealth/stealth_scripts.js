/**
 * STEALTH INJECTION SCRIPTS
 * Comprehensive fingerprint spoofing for anti-detect browser profiles.
 * Injected via Playwright's addInitScript before any page JS runs.
 *
 * Parameterized via double-brace tokens replaced at runtime by Python.
 */

(function() {
    'use strict';

    // =========================================================================
    // NAVIGATOR OVERRIDES
    // =========================================================================

    // Kill the biggest red flag first
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
        configurable: true
    });
    // Belt-and-suspenders: some detectors check the prototype
    delete Object.getPrototypeOf(navigator).webdriver;

    Object.defineProperty(navigator, 'deviceMemory', {
        get: () => {{DEVICE_MEMORY}},
        configurable: true
    });

    Object.defineProperty(navigator, 'hardwareConcurrency', {
        get: () => {{HARDWARE_CONCURRENCY}},
        configurable: true
    });

    Object.defineProperty(navigator, 'platform', {
        get: () => '{{PLATFORM}}',
        configurable: true
    });

    Object.defineProperty(navigator, 'languages', {
        get: () => Object.freeze({{LANGUAGES}}),
        configurable: true
    });

    Object.defineProperty(navigator, 'language', {
        get: () => '{{LANGUAGE}}',
        configurable: true
    });

    Object.defineProperty(navigator, 'vendor', {
        get: () => '{{VENDOR}}',
        configurable: true
    });

    // =========================================================================
    // PLUGINS (Chrome-realistic)
    // =========================================================================

    const makePluginArray = (plugins) => {
        const arr = Object.create(PluginArray.prototype);
        const items = [];
        plugins.forEach((p, i) => {
            const plugin = Object.create(Plugin.prototype);
            Object.defineProperties(plugin, {
                name:        { get: () => p.name },
                filename:    { get: () => p.filename },
                description: { get: () => p.description },
                length:      { get: () => p.mimeTypes.length },
            });
            p.mimeTypes.forEach((mt, j) => {
                const mime = Object.create(MimeType.prototype);
                Object.defineProperties(mime, {
                    type:           { get: () => mt.type },
                    suffixes:       { get: () => mt.suffixes },
                    description:    { get: () => mt.description },
                    enabledPlugin:  { get: () => plugin },
                });
                Object.defineProperty(plugin, j, { get: () => mime });
                Object.defineProperty(plugin, mt.type, { get: () => mime });
            });
            items.push(plugin);
            Object.defineProperty(arr, i, { get: () => plugin });
            Object.defineProperty(arr, p.name, { get: () => plugin });
        });
        Object.defineProperty(arr, 'length', { get: () => items.length });
        arr.item = (i) => items[i] || null;
        arr.namedItem = (n) => items.find(p => p.name === n) || null;
        arr.refresh = () => {};
        arr[Symbol.iterator] = function* () { yield* items; };
        return arr;
    };

    Object.defineProperty(navigator, 'plugins', {
        get: () => makePluginArray([
            {
                name: 'Chrome PDF Plugin',
                filename: 'internal-pdf-viewer',
                description: 'Portable Document Format',
                mimeTypes: [
                    { type: 'application/x-google-chrome-pdf', suffixes: 'pdf', description: 'Portable Document Format' }
                ]
            },
            {
                name: 'Chrome PDF Viewer',
                filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai',
                description: '',
                mimeTypes: [
                    { type: 'application/pdf', suffixes: 'pdf', description: '' }
                ]
            },
            {
                name: 'Native Client',
                filename: 'internal-nacl-plugin',
                description: '',
                mimeTypes: [
                    { type: 'application/x-nacl', suffixes: '', description: 'Native Client Executable' },
                    { type: 'application/x-pnacl', suffixes: '', description: 'Portable Native Client Executable' }
                ]
            }
        ]),
        configurable: true
    });

    Object.defineProperty(navigator, 'mimeTypes', {
        get: () => {
            const arr = Object.create(MimeTypeArray.prototype);
            const mimes = [
                { type: 'application/x-google-chrome-pdf', suffixes: 'pdf', description: 'Portable Document Format' },
                { type: 'application/pdf', suffixes: 'pdf', description: '' },
                { type: 'application/x-nacl', suffixes: '', description: 'Native Client Executable' },
                { type: 'application/x-pnacl', suffixes: '', description: 'Portable Native Client Executable' }
            ];
            mimes.forEach((m, i) => {
                const mime = Object.create(MimeType.prototype);
                Object.defineProperties(mime, {
                    type:        { get: () => m.type },
                    suffixes:    { get: () => m.suffixes },
                    description: { get: () => m.description },
                });
                Object.defineProperty(arr, i, { get: () => mime });
                Object.defineProperty(arr, m.type, { get: () => mime });
            });
            Object.defineProperty(arr, 'length', { get: () => mimes.length });
            arr.item = (i) => mimes[i] ? arr[i] : null;
            arr.namedItem = (n) => arr[n] || null;
            return arr;
        },
        configurable: true
    });

    // =========================================================================
    // SCREEN OVERRIDES
    // =========================================================================

    const screenProps = {
        width:      {{SCREEN_WIDTH}},
        height:     {{SCREEN_HEIGHT}},
        availWidth: {{SCREEN_WIDTH}},
        availHeight:{{SCREEN_HEIGHT}} - 40,
        colorDepth: {{COLOR_DEPTH}},
        pixelDepth: {{PIXEL_DEPTH}},
    };

    for (const [prop, val] of Object.entries(screenProps)) {
        Object.defineProperty(screen, prop, {
            get: () => val,
            configurable: true
        });
    }

    // =========================================================================
    // WEBGL FINGERPRINT
    // =========================================================================

    const spoofWebGL = (proto) => {
        const originalGetParameter = proto.getParameter;
        proto.getParameter = function(param) {
            // UNMASKED_VENDOR_WEBGL
            if (param === 37445) return '{{WEBGL_VENDOR}}';
            // UNMASKED_RENDERER_WEBGL
            if (param === 37446) return '{{WEBGL_RENDERER}}';
            return originalGetParameter.call(this, param);
        };

        const originalGetExtension = proto.getExtension;
        proto.getExtension = function(name) {
            const ext = originalGetExtension.call(this, name);
            if (name === 'WEBGL_debug_renderer_info') {
                return ext; // Let it through so getParameter intercepts
            }
            return ext;
        };
    };

    if (typeof WebGLRenderingContext !== 'undefined') {
        spoofWebGL(WebGLRenderingContext.prototype);
    }
    if (typeof WebGL2RenderingContext !== 'undefined') {
        spoofWebGL(WebGL2RenderingContext.prototype);
    }

    // =========================================================================
    // CANVAS NOISE INJECTION
    // =========================================================================

    // Deterministic seed per profile so canvas hash is stable but unique
    let _canvasSeed = {{CANVAS_SEED}};
    const canvasRng = () => {
        _canvasSeed = (_canvasSeed * 16807 + 0) % 2147483647;
        return (_canvasSeed - 1) / 2147483646;
    };

    const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(...args) {
        const ctx = this.getContext('2d');
        if (ctx && this.width > 0 && this.height > 0) {
            try {
                const imageData = ctx.getImageData(0, 0, this.width, this.height);
                // Modify ~0.1% of pixels with deterministic noise
                for (let i = 0; i < imageData.data.length; i += 4) {
                    if (canvasRng() < 0.001) {
                        imageData.data[i]     = Math.min(255, Math.max(0, imageData.data[i]     + Math.floor(canvasRng() * 3) - 1));
                        imageData.data[i + 1] = Math.min(255, Math.max(0, imageData.data[i + 1] + Math.floor(canvasRng() * 3) - 1));
                        imageData.data[i + 2] = Math.min(255, Math.max(0, imageData.data[i + 2] + Math.floor(canvasRng() * 3) - 1));
                    }
                }
                ctx.putImageData(imageData, 0, 0);
            } catch(e) {
                // Cross-origin canvas, can't modify
            }
        }
        return originalToDataURL.apply(this, args);
    };

    const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
    CanvasRenderingContext2D.prototype.getImageData = function(...args) {
        const imageData = originalGetImageData.apply(this, args);
        for (let i = 0; i < imageData.data.length; i += 4) {
            if (canvasRng() < 0.001) {
                imageData.data[i] = Math.min(255, Math.max(0, imageData.data[i] + Math.floor(canvasRng() * 3) - 1));
            }
        }
        return imageData;
    };

    // =========================================================================
    // AUDIO FINGERPRINT NOISE
    // =========================================================================

    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (AudioCtx) {
        const origCreateAnalyser = AudioCtx.prototype.createAnalyser;
        AudioCtx.prototype.createAnalyser = function() {
            const analyser = origCreateAnalyser.apply(this, arguments);

            const origGetFloat = analyser.getFloatFrequencyData.bind(analyser);
            analyser.getFloatFrequencyData = function(array) {
                origGetFloat(array);
                for (let i = 0; i < array.length; i++) {
                    array[i] += (canvasRng() - 0.5) * 0.0001;
                }
            };
            return analyser;
        };

        const origCreateOscillator = AudioCtx.prototype.createOscillator;
        AudioCtx.prototype.createOscillator = function() {
            const osc = origCreateOscillator.apply(this, arguments);
            return osc; // Noise injected at analyser level
        };
    }

    // =========================================================================
    // BATTERY API
    // =========================================================================

    if ('getBattery' in navigator) {
        const batteryLevel = 0.75 + canvasRng() * 0.2; // 75-95%
        navigator.getBattery = () => Promise.resolve({
            charging: true,
            chargingTime: 0,
            dischargingTime: Infinity,
            level: Math.round(batteryLevel * 100) / 100,
            addEventListener: () => {},
            removeEventListener: () => {},
            dispatchEvent: () => true,
            onchargingchange: null,
            onchargingtimechange: null,
            ondischargingtimechange: null,
            onlevelchange: null,
        });
    }

    // =========================================================================
    // TIMEZONE (Intl.DateTimeFormat)
    // =========================================================================

    const OriginalDTF = Intl.DateTimeFormat;
    Intl.DateTimeFormat = function(locales, options) {
        options = options || {};
        if (!options.timeZone) {
            options.timeZone = '{{TIMEZONE}}';
        }
        return new OriginalDTF(locales, options);
    };
    Intl.DateTimeFormat.prototype = OriginalDTF.prototype;
    Intl.DateTimeFormat.supportedLocalesOf = OriginalDTF.supportedLocalesOf;

    // Also override Date.prototype.getTimezoneOffset for consistency
    // This is tricky - we approximate based on UTC offset
    // The actual offset depends on DST, but detection sites mainly check consistency
    // with Intl.DateTimeFormat, so we leave getTimezoneOffset alone and let
    // Playwright's timezone_id handle it.

    // =========================================================================
    // CLIENT HINTS (sec-ch-ua headers are set via Playwright context)
    // These JS-side overrides cover navigator.userAgentData
    // =========================================================================

    if ('userAgentData' in navigator) {
        const brands = {{UA_BRANDS}};
        const mobile = false;
        const platformName = '{{UA_PLATFORM}}';
        const platformVersion = '{{UA_PLATFORM_VERSION}}';
        const architecture = '{{UA_ARCHITECTURE}}';
        const model = '';
        const fullVersionList = {{UA_FULL_VERSION_LIST}};

        Object.defineProperty(navigator, 'userAgentData', {
            get: () => ({
                brands: brands,
                mobile: mobile,
                platform: platformName,
                getHighEntropyValues: (hints) => Promise.resolve({
                    brands: brands,
                    mobile: mobile,
                    platform: platformName,
                    platformVersion: platformVersion,
                    architecture: architecture,
                    model: model,
                    uaFullVersion: fullVersionList[0]?.version || '',
                    fullVersionList: fullVersionList,
                    bitness: '64',
                    wow64: false,
                }),
                toJSON: () => ({ brands, mobile, platform: platformName }),
            }),
            configurable: true
        });
    }

    // =========================================================================
    // WEBRTC IP LEAK PREVENTION
    // =========================================================================

    // Disable WebRTC peer connections to prevent IP leaks
    if (typeof RTCPeerConnection !== 'undefined') {
        const OriginalRTC = RTCPeerConnection;
        window.RTCPeerConnection = function(config, constraints) {
            // Force through relay (TURN) only - blocks STUN IP discovery
            if (config && config.iceServers) {
                config.iceServers = [];
            }
            config = config || {};
            config.iceTransportPolicy = 'relay';
            return new OriginalRTC(config, constraints);
        };
        window.RTCPeerConnection.prototype = OriginalRTC.prototype;
        // Some sites check these aliases
        window.webkitRTCPeerConnection = window.RTCPeerConnection;
        window.mozRTCPeerConnection = undefined;
    }

    // =========================================================================
    // MEDIA DEVICES (consistent device enumeration)
    // =========================================================================

    if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
        const origEnum = navigator.mediaDevices.enumerateDevices.bind(navigator.mediaDevices);
        navigator.mediaDevices.enumerateDevices = async () => {
            return [
                { deviceId: 'default', kind: 'audioinput',  label: '', groupId: 'default' },
                { deviceId: 'comms',   kind: 'audioinput',  label: '', groupId: 'comms' },
                { deviceId: 'default', kind: 'audiooutput', label: '', groupId: 'default' },
                { deviceId: 'default', kind: 'videoinput',  label: '', groupId: 'default' },
            ];
        };
    }

    // =========================================================================
    // CHROME RUNTIME (make it look like a real Chrome install)
    // =========================================================================

    if (!window.chrome) {
        window.chrome = {};
    }
    if (!window.chrome.runtime) {
        window.chrome.runtime = {
            OnInstalledReason: { CHROME_UPDATE: 'chrome_update', INSTALL: 'install', SHARED_MODULE_UPDATE: 'shared_module_update', UPDATE: 'update' },
            OnRestartRequiredReason: { APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' },
            PlatformArch: { ARM: 'arm', ARM64: 'arm64', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
            PlatformNaclArch: { ARM: 'arm', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
            PlatformOs: { ANDROID: 'android', CROS: 'cros', LINUX: 'linux', MAC: 'mac', OPENBSD: 'openbsd', WIN: 'win' },
            RequestUpdateCheckStatus: { NO_UPDATE: 'no_update', THROTTLED: 'throttled', UPDATE_AVAILABLE: 'update_available' },
            connect: () => ({ onMessage: { addListener: () => {} }, postMessage: () => {} }),
            sendMessage: () => {},
            id: undefined,
        };
    }
    if (!window.chrome.csi) {
        window.chrome.csi = () => ({
            onloadT: Date.now(),
            startE: Date.now(),
            pageT: Math.random() * 1000 + 500,
            tran: 15,
        });
    }
    if (!window.chrome.loadTimes) {
        window.chrome.loadTimes = () => ({
            commitLoadTime: Date.now() / 1000,
            connectionInfo: 'h2',
            finishDocumentLoadTime: Date.now() / 1000 + Math.random(),
            finishLoadTime: Date.now() / 1000 + Math.random(),
            firstPaintAfterLoadTime: 0,
            firstPaintTime: Date.now() / 1000 + Math.random() * 0.5,
            navigationType: 'Other',
            npnNegotiatedProtocol: 'h2',
            requestTime: Date.now() / 1000 - Math.random(),
            startLoadTime: Date.now() / 1000 - Math.random(),
            wasAlternateProtocolAvailable: false,
            wasFetchedViaSpdy: true,
            wasNpnNegotiated: true,
        });
    }

    // =========================================================================
    // PERMISSION API SPOOFING
    // =========================================================================

    const originalQuery = Permissions.prototype.query;
    Permissions.prototype.query = function(parameters) {
        // notifications permission should return 'prompt', not 'denied'
        if (parameters.name === 'notifications') {
            return Promise.resolve({ state: 'prompt', onchange: null });
        }
        return originalQuery.call(this, parameters);
    };

    // =========================================================================
    // IFRAME CONTENTWINDOW
    // =========================================================================

    // Ensure iframes have proper contentWindow (some detectors check this)
    try {
        const frame = document.createElement('iframe');
        if (frame.contentWindow) {
            Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
                get: function() {
                    return this._contentWindow || null;
                }
            });
        }
    } catch(e) {}

    // =========================================================================
    // FUNCTION toString PROTECTION
    // =========================================================================

    // Detectors check if overridden functions have 'native code' in toString
    const nativeToString = Function.prototype.toString;
    const spoofedFns = new Set();

    const patchToString = (fn, original) => {
        spoofedFns.add(fn);
        const handler = {
            apply: function(target, thisArg, args) {
                if (spoofedFns.has(thisArg)) {
                    return `function ${thisArg.name || ''}() { [native code] }`;
                }
                return nativeToString.apply(thisArg, args);
            }
        };
        Function.prototype.toString = new Proxy(Function.prototype.toString, handler);
    };

    // Protect the overrides we just applied
    spoofedFns.add(navigator.getBattery);
    spoofedFns.add(Permissions.prototype.query);

})();
