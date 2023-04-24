const utils = {
  get userAgent() {
    const ua = navigator.userAgent;

    const soup = new Set([]);
    const flavor = {
      major: 0,
      soup: soup,
      is: (value) => soup.has(value),
    };

    if (/\bMobile\b/.test(ua)) {
      soup.add('mobile');
    }

    // Synchronous -- order of tests is important
    let match;
    if ((match = /\bFirefox\/(\d+)/.exec(ua)) !== null) {
      flavor.major = parseInt(match[1], 10) || 0;
      soup.add('mozilla').add('firefox');
    } else if ((match = /\bEdge\/(\d+)/.exec(ua)) !== null) {
      flavor.major = parseInt(match[1], 10) || 0;
      soup.add('microsoft').add('edge');
    } else if ((match = /\bOPR\/(\d+)/.exec(ua)) !== null) {
      const reEx = /\bChrom(?:e|ium)\/([\d.]+)/;
      if (reEx.test(ua)) { match = reEx.exec(ua); }
      flavor.major = parseInt(match[1], 10) || 0;
      soup.add('opera').add('chromium');
    } else if ((match = /\bChromium\/(\d+)/.exec(ua)) !== null) {
      flavor.major = parseInt(match[1], 10) || 0;
      soup.add('chromium');
    } else if ((match = /\bChrome\/(\d+)/.exec(ua)) !== null) {
      flavor.major = parseInt(match[1], 10) || 0;
      soup.add('google').add('chromium');
    } else if ((match = /\bSafari\/(\d+)/.exec(ua)) !== null) {
      flavor.major = parseInt(match[1], 10) || 0;
      soup.add('apple').add('safari');
    }

    Object.defineProperty(this, 'userAgent', { value: flavor });
    return flavor;
  },

  escapeRegExp(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  },

  lang(key, args) {
    const str = LANG[key];
    if (typeof str !== 'string') { return key; }
    const a = Object.assign({'': '%'}, args);
    return str.replace(/%(\w*)%/g, (_, key) => a[key] || '');
  },

  async wait(ms) {
    await new Promise(r => setTimeout(r, ms));
  },

  async xhr(params = {}) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      if (params.onreadystatechange) {
        xhr.onreadystatechange = function (event) {
          params.onreadystatechange(xhr);
        };
      }

      xhr.onload = function (event) {
        resolve(xhr);
      };

      xhr.onabort = function (event) {
        // resolve with no param
        resolve();
      };

      xhr.onerror = function (event) {
        // No additional useful information can be get from the event object.
        reject(new Error("Network request failed."));
      };

      xhr.ontimeout = function (event) {
        reject(new Error("Request timeout."));
      };

      xhr.responseType = params.responseType;
      xhr.open(params.method || "GET", params.url, true);

      if (params.timeout) { xhr.timeout = params.timeout; }

      // Must call setRequestHeader() after open(), but before send().
      if (params.requestHeaders) {
        for (let header in params.requestHeaders) {
          xhr.setRequestHeader(header, params.requestHeaders[header]);
        }
      }

      xhr.send(params.formData);
    });
  },

  /**
   * Wrapped method for common WSB requests
   */
  async wsb(params = {}) {
    const xhr = await this.xhr(params);
    if (xhr.response && xhr.response.error && xhr.response.error.message) {
      throw new Error(xhr.response.error.message);
    } else if (!(xhr.status >= 200 && xhr.status <= 206)) {
      const statusText = xhr.status + (xhr.statusText ? " " + xhr.statusText : "");
      throw new Error(statusText);
    }
    return xhr;
  },

  getTargetUrl(url) {
    const u = new URL(url || document.location.href);
    u.search = u.hash = '';
    return u.href;
  },

  async acquireToken(url) {
    const xhr = await this.wsb({
        url: url + '?a=token&f=json',
        responseType: 'json',
        method: "POST",
    });
    return xhr.response.data;
  },
};
