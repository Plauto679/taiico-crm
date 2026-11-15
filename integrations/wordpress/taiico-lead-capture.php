/** Taiico capture bridge. Install through Code Snippets (global).
 * Replace __WEBHOOK_KEY__ during deployment; never expose it to the browser.
 */
add_action('rest_api_init', function () {
    register_rest_route('taiico/v1', '/lead/(?P<kind>clientes|agentes)', array(
        'methods' => 'POST', 'permission_callback' => '__return_true',
        'callback' => function (WP_REST_Request $request) {
            if (strlen($request->get_body()) > 16384) return new WP_Error('too_large', 'Formulario demasiado grande.', array('status' => 413));
            $input = $request->get_json_params();
            if (!is_array($input)) return new WP_Error('invalid_form', 'Revisa los datos del formulario.', array('status' => 422));
            $ip = isset($_SERVER['REMOTE_ADDR']) ? $_SERVER['REMOTE_ADDR'] : 'unknown';
            $rate_key = 'taiico_lead_' . hash('sha256', $ip);
            $attempts = (int) get_transient($rate_key);
            if ($attempts >= 10) return new WP_Error('rate_limit', 'Espera unos minutos antes de volver a intentarlo.', array('status' => 429));
            set_transient($rate_key, $attempts + 1, 10 * MINUTE_IN_SECONDS);
            if (!empty($input['website'])) return new WP_Error('invalid_form', 'No se pudo enviar el formulario.', array('status' => 422));
            $allowed = array('nombre','telefono','correo','ciudad','interes','consentimiento','whatsapp','utm_source','utm_medium','utm_campaign','utm_content','website');
            $data = array();
            foreach ($allowed as $field) {
                $value = isset($input[$field]) ? $input[$field] : '';
                if (!is_scalar($value)) return new WP_Error('invalid_form', 'Revisa los datos del formulario.', array('status' => 422));
                $data[$field] = sanitize_text_field((string) $value);
            }
            $result = wp_remote_post('https://taiico-crm.com/api/captacion/elementor/' . $request['kind'] . '?key=__WEBHOOK_KEY__', array(
                'timeout' => 20, 'redirection' => 0,
                'headers' => array('Content-Type' => 'application/json'),
                'body' => wp_json_encode($data),
            ));
            if (is_wp_error($result)) return new WP_Error('crm_unavailable', 'No pudimos confirmar tu solicitud. Inténtalo de nuevo; tus datos siguen en el formulario.', array('status' => 503));
            $status = wp_remote_retrieve_response_code($result);
            $body = json_decode(wp_remote_retrieve_body($result), true);
            if ($status !== 200 || empty($body['success'])) {
                $message = $status === 422 ? 'Revisa el teléfono, el correo y la autorización de contacto.' : 'No pudimos confirmar tu solicitud. Inténtalo nuevamente.';
                return new WP_Error('crm_rejected', $message, array('status' => $status === 422 ? 422 : 503));
            }
            $response = new WP_REST_Response(array('success' => true), 200);
            $response->header('Cache-Control', 'no-store');
            return $response;
        }
    ));
});

add_shortcode('taiico_captacion', function ($attributes) {
    $a = shortcode_atts(array('tipo' => 'clientes'), $attributes);
    $kind = $a['tipo'] === 'agentes' ? 'agentes' : 'clientes';
    $agent = $kind === 'agentes';
    $interests = $agent ? array('Quiero iniciar como agente', 'Ya soy agente', 'Quiero conocer el modelo') : array('Vida', 'Gastos médicos', 'Auto', 'Hogar', 'Empresa', 'Asesoría general');
    ob_start(); ?>
    <div class="taiico-capture">
      <form class="taiico-capture-form" data-kind="<?php echo esc_attr($kind); ?>" aria-label="Solicitud Taiico <?php echo esc_attr($kind); ?>">
        <label>Nombre completo<input name="nombre" type="text" autocomplete="name" minlength="2" maxlength="150" required></label>
        <label>Teléfono<input name="telefono" type="tel" autocomplete="tel" maxlength="30" placeholder="10 dígitos en México o +código de país" required></label>
        <label>Correo electrónico (opcional)<input name="correo" type="email" autocomplete="email" maxlength="254"></label>
        <label>Ciudad y estado<input name="ciudad" type="text" autocomplete="address-level2" minlength="2" maxlength="120" placeholder="Ej. Monterrey, Nuevo León" required></label>
        <label><?php echo $agent ? '¿En qué etapa estás?' : '¿Qué te gustaría proteger?'; ?><select name="interes" required><option value="">Selecciona una opción</option><?php foreach ($interests as $interest) { ?><option value="<?php echo esc_attr($interest); ?>"><?php echo esc_html($interest); ?></option><?php } ?></select></label>
        <p class="taiico-privacy">Usaremos tus datos para atender esta solicitud y darle seguimiento con <?php echo $agent ? 'el equipo de reclutamiento de Taiico' : 'el equipo y un agente de Taiico'; ?>. <a href="https://taiico.com/aviso-de-privacidad/" target="_blank" rel="noopener">Consulta nuestro aviso de privacidad.</a></p>
        <label class="taiico-check"><input name="consentimiento" type="checkbox" value="si" required><span>Autorizo a Taiico a contactarme para atender esta solicitud.</span></label>
        <label class="taiico-check"><input name="whatsapp" type="checkbox" value="si"><span>También autorizo el contacto por WhatsApp para esta solicitud (opcional).</span></label>
        <div class="taiico-hp" aria-hidden="true"><label>Deja este campo vacío<input name="website" tabindex="-1" autocomplete="off"></label></div>
        <button type="submit" disabled><?php echo $agent ? 'Quiero conocer Taiico' : 'Solicitar asesoría'; ?></button>
        <div class="taiico-result" role="status" aria-live="polite" tabindex="-1" hidden></div>
        <noscript>Activa JavaScript para enviar el formulario o escribe a atencion.clientes@taiico.com.</noscript>
      </form>
    </div>
    <?php return ob_get_clean();
});

add_action('wp_head', function () { ?>
<style id="taiico-capture-style">
.taiico-capture{display:block;width:100%;font-family:Inter,Arial,sans-serif;color:#17324d;text-align:left}.taiico-capture-form{display:flex;flex-direction:column;gap:1.25rem;margin:0}.taiico-capture label{display:flex;flex-direction:column;gap:.5rem;font-size:.95rem;font-weight:600;color:#17324d}.taiico-capture input:not([type=checkbox]),.taiico-capture select{box-sizing:border-box;width:100%;min-height:3rem;border:1px solid #8d9cab;border-radius:.4rem;background:#fff;color:#17324d;padding:.8rem;font:inherit;font-weight:400}.taiico-capture input:focus,.taiico-capture select:focus,.taiico-capture button:focus{outline:2px solid #34587c;outline-offset:3px}.taiico-capture .taiico-check{display:flex;flex-direction:row;align-items:flex-start;gap:.75rem;font-weight:400;font-size:.9rem;line-height:1.5}.taiico-capture input[type=checkbox]{appearance:auto;width:1.2rem;height:1.2rem;flex:0 0 1.2rem;margin:.15rem 0 0;accent-color:#34587c}.taiico-capture .taiico-privacy{font-size:.85rem;line-height:1.6;margin:0;color:#40556a}.taiico-capture a{color:#234e79;text-decoration:underline}.taiico-capture button{background:#34587c;color:#fff;border:0;border-radius:.5rem;padding:1rem 1.5rem;font-size:1rem;font-weight:600;cursor:pointer}.taiico-capture button:hover{background:#203d59}.taiico-capture button:disabled{opacity:.6;cursor:wait}.taiico-capture .taiico-hp{position:absolute;left:-10000px;width:1px;height:1px;overflow:hidden}.taiico-capture .taiico-result{padding:1rem;border-radius:.5rem;font-size:.95rem;line-height:1.5}.taiico-capture .taiico-result[data-success=true]{background:#e3f2e7;color:#17462c}.taiico-capture .taiico-result[data-success=false]{background:#fff1ec;color:#87371f}.taiico-capture [hidden]{display:none!important}
</style>
<?php });

add_action('wp_footer', function () { ?>
<script id="taiico-capture-script">
(function(){
function init(){
var incoming=new URLSearchParams(window.location.search);
if(incoming.get('utm_source'))document.querySelectorAll('a[href]').forEach(function(a){try{var u=new URL(a.href,location.href);if(u.origin===location.origin&&['/seguros/asesoria-general/','/se-parte-de-nuestro-equipo/'].includes(u.pathname)){['utm_source','utm_medium','utm_campaign','utm_content'].forEach(function(k){if(incoming.get(k))u.searchParams.set(k,incoming.get(k).slice(0,100));});a.href=u.toString();}}catch(e){}});
document.querySelectorAll('.taiico-capture-form').forEach(function(form){
 if(form.dataset.ready)return;form.dataset.ready='1';var button=form.querySelector('button[type=submit]');button.disabled=false;
 form.addEventListener('submit',async function(event){
  event.preventDefault(); if(form.dataset.busy==='1'||!form.reportValidity())return;
  var payload=Object.fromEntries(new FormData(form));payload.whatsapp=payload.whatsapp||'no';
  var query=new URLSearchParams(window.location.search);['utm_source','utm_medium','utm_campaign','utm_content'].forEach(function(k){payload[k]=(query.get(k)||'').slice(0,100);});
  var output=form.querySelector('.taiico-result');output.hidden=true;form.dataset.busy='1';button.disabled=true;var original=button.textContent;button.textContent='Enviando…';
  try{
   var response=await fetch('/wp-json/taiico/v1/lead/'+form.dataset.kind,{method:'POST',headers:{'Content-Type':'application/json'},credentials:'omit',body:JSON.stringify(payload)});
   var data=await response.json();if(!response.ok||data.success!==true)throw new Error(data.message||'No pudimos confirmar tu solicitud. Inténtalo nuevamente.');
   output.textContent='Gracias. Tu solicitud quedó registrada. El equipo de Taiico se pondrá en contacto contigo.';output.dataset.success='true';form.reset();
  }catch(error){output.textContent=error.message||'No pudimos confirmar tu solicitud. Revisa tu conexión e inténtalo de nuevo.';output.dataset.success='false';}
  finally{output.hidden=false;output.focus();form.dataset.busy='0';button.disabled=false;button.textContent=original;}
 });
});}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
</script>
<?php });

// Replace an Elementor text marker after widget sanitization, preserving native form markup.
$taiico_render_capture = function ($content) {
    foreach (array('clientes', 'agentes') as $kind) {
        $marker = '{{TAIICO_CAPTACION_' . strtoupper($kind) . '}}';
        if (strpos($content, $marker) !== false) {
            $content = str_replace($marker, do_shortcode('[taiico_captacion tipo="' . $kind . '"]'), $content);
        }
    }
    return $content;
};
add_filter('the_content', $taiico_render_capture, 99);
add_filter('elementor/frontend/the_content', $taiico_render_capture, 99);
