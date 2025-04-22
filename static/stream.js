// WebSocket ile canlı ekran/webcam stream alma (örnek, backend'de websocket veya benzeri stream endpoint gereklidir)
function startStream(clientId, type) {
    const imgElem = document.getElementById(type+"-stream-img");
    let ws = new WebSocket(`ws://${location.host}/stream/${type}/${clientId}`);
    ws.binaryType = 'arraybuffer';
    ws.onmessage = function(event) {
        let blob = new Blob([event.data], {type: 'image/jpeg'});
        let url = URL.createObjectURL(blob);
        imgElem.src = url;
    };
    ws.onclose = function() {
        imgElem.src = '';
    };
    return ws;
}
function stopStream(ws) {
    if(ws) ws.close();
}
