import React from 'react'
import {load_script_callback} from '../utils'

const GOOGLE_MAPS_KEY = process.env.REACT_APP_GOOGLE_MAPS_KEY
const GOOGLE_MAPS_JS = `https://maps.googleapis.com/maps/api/js?key=${GOOGLE_MAPS_KEY}&callback=<callback-function>`
const MAP_ID = 'googe-maps'

export default class Map extends React.Component {
  constructor (props) {
    super(props)
    this.update_map = this.update_map.bind(this)
  }

  async componentDidMount () {
    this.update_map()
  }

  componentDidUpdate () {
    this.update_map()
  }

  update_map () {
    clearInterval(window._map_update)
    window._map_update = setTimeout(this.update_map_direct.bind(this), 100)
  }

  async update_map_direct () {
    const el = document.getElementById(MAP_ID)
    if (!el) {
      return
    }
    const loc = this.props.geolocation
    await load_script_callback(GOOGLE_MAPS_JS)
    if (el.childElementCount === 0 && window.google) {
      this.map = new window.google.maps.Map(el, {
        center: loc,
        zoom: loc.zoom || 14,
        fullscreenControl: false,
      })
      this.marker = new window.google.maps.Marker({
        position: loc,
        title: loc.name,
        map: this.map,
        draggable: Boolean(this.props.onDrag),
      })
      this.marker.addListener('dragend', this.props.onDrag)
      window.gmaps_geocoder = new window.google.maps.Geocoder()
      if (this.props.click_handler) {
        window.google.maps.event.addListener(this.map, 'click', this.props.click_handler)
      }
    } else {
      this.marker.setPosition(loc)
      this.marker.setTitle(loc.name)
      const bounds = this.map.getBounds()
      if (bounds && !bounds.contains(this.marker.getPosition())) {
        this.map.setCenter(loc)
      }
    }
  }

  render () {
    const loc = this.props.geolocation || {}
    if (Number.isFinite(loc.lat) && Number.isFinite(loc.lng)) {
      return <div id={MAP_ID} className="mt-2" style={{height: this.props.height || 300}}/>
    } else {
      return <div/>
    }
  }
}
