import React from 'react'
import {load_script, window_property} from '../utils'

const GOOGLE_MAPS_KEY = process.env.REACT_APP_GOOGLE_MAPS_KEY
const GOOGLE_MAPS_JS = `https://maps.googleapis.com/maps/api/js?key=${GOOGLE_MAPS_KEY}`

export default class Map extends React.Component {
  constructor (props) {
    super(props)
    this.update_map = this.update_map.bind(this)
    this.el_id = 'googe-maps-' + Math.random().toString(36).substring(2, 10)
  }

  async componentDidMount () {
    this.update_map()
  }

  componentDidUpdate () {
    this.update_map()
  }

  async update_map () {
    const el = document.getElementById(this.el_id)
    if (!el) {
      return
    }
    const loc = this.props.geolocation
    await load_script(GOOGLE_MAPS_JS)
    const google = await window_property('google')
    if (el.childElementCount === 0) {
      this.map = new google.maps.Map(el, {
        center: loc,
        zoom: loc.zoom || 14,
        fullscreenControl: false,
        mapTypeControl: false,
        streetViewControl: false,
      })
      this.marker = new google.maps.Marker({
        position: loc,
        title: loc.name,
        map: this.map,
        draggable: Boolean(this.props.onDrag),
      })
      this.marker.addListener('dragend', this.props.onDrag)
      window.gmaps_geocoder = new google.maps.Geocoder()
      if (this.props.click_handler) {
        google.maps.event.addListener(this.map, 'click', this.props.click_handler)
      }
    } else if (this.marker) {
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
      return <div id={this.el_id} className={this.props.className || 'mt-2'}
                  style={{height: this.props.height || 300, width: this.props.width}}/>
    } else {
      return this.props.children || null
    }
  }
}
