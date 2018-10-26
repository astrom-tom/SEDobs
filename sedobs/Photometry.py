'''
The SPARTAN SIM Project
-------------------
Modul dealing with the photometric computation

@Author R. THOMAS
@year   2017
@place  UV/LAM/UCBJ
@License: GNU public licence v3.0 - see LICENCE.txt
'''
###standard library
import copy

####Python General Libraries
import numpy
import scipy.constants as const


##SPARTAN libraries
from . import units
from . import filters

class Photometry:
    """
    This class deals with action that need to retrieve
    a filter name or to get filter data
    It implements 3 methods:
    """

    def __init__(self, filterfile):
        """
        Class Constructor defining one attributes:

        self. Filterfile    The location of the filter file, and the file
        """
        ###unit convertor
        ##speed of light
        c = const.c
        ##to angstrom/s
        ca = c * 1e10
        #factor from l*l*F(l) to F(J)
        self.toJy = 1e23/ca
        self.filterfile = filterfile

    def Normalise_template(self, wave, flux, band, Norm, sky):
        '''
        this methods normalise the template (wave, flux) to the
        maganitude (Norm) in the given band
        '''
        ##1 - Compute the magnitude
        magAB, fluxmag, Leff, FWHM = self.Compute_mag_from_template(wave, flux, band, sky)

        ##2 - Convert the normalisation magnitude to flux
        fluxNormmag = self.mag2flux(Norm, Leff)

        ##3 - compute the ratio of flux
        r = fluxNormmag / fluxmag
        
        ##4 - normalise the template
        Norm_flux = r * flux

        ###for checking we recompute the magnitude from the normalized
        ###flux
        #newmag, newfluxmag, Leff, FWHM = self.Compute_mag_from_template(wave, Norm_flux, band)

        #print(newmag, newfluxmag)

        return Norm_flux, r

    def simulate_photo(self, wave, flux, band_list, conf, sky):
        '''
        Method that simulate the photometry. First we compute
        the magnitude in the bands and then the errors
        Parameter:
        ----------
        wave        list, of observed wavelength
        flux        list, of observed flux (normalised) 
        band_list   list, of band and error
        conf        dict, of configuration from user configuration
        sim_sky     obj, sky atmosphere properties
        '''
        ###extract band names from the the list
        band_names = band_list.keys()
        
        ###loop over each band
        Photo_sim = {}
        for i in band_names:
            Photo_sim[i] = {}
            ##compute the magnitude in the band
            magAB, fluxAB, Leff, FWHM= self.Compute_mag_from_template(wave, flux, \
                    band_list[i], sky)

            ###and simulate the error
            err = self.simulate_error_phot(band_list[i][2], band_list[i][3] )

            ###simulate offset
            zp = band_list[i][1]

            ###add the error to the measurement
            magABzp =  magAB+zp
            fluxABzp = self.mag2flux(magABzp, Leff)
            flux_err = numpy.abs(err)*fluxAB*numpy.log(10)/2.5

            ###take care of unit conversion, is neeeded
            if conf['flux_unit'] == 'Jy':
                flux_errp = (fluxAB + flux_err) * Leff * Leff * self.toJy
                flux_errm = (fluxAB - flux_err) * Leff * Leff * self.toJy
                flux_err = (flux_errp-flux_errm)/2
                fluxAB = fluxAB * Leff * Leff * self.toJy
                fluxABzp = fluxABzp * Leff * Leff * self.toJy

            if conf['flux_unit'] == 'muJy':
                flux_errp = (fluxAB + flux_err) * Leff * Leff * self.toJy * 1e6
                flux_errm = (fluxAB - flux_err) * Leff * Leff * self.toJy * 1e6
                flux_err = (flux_errp-flux_errm)/2 
                fluxAB = fluxAB * Leff * Leff * self.toJy * 1e6
                fluxABzp = fluxABzp * Leff * Leff * self.toJy * 1e6

            if conf['wave_unit'] == 'log_ang':
                FWHM = numpy.log10(Leff + FWHM/2) - numpy.log10(Leff-FWHM/2)
                Leff = numpy.log10(Leff)

            ##and save it
            Photo_sim[i]['Measori'] = magAB  ##Template real magnitude
            Photo_sim[i]['Fluxori'] = fluxAB ##Flux rea; Magnitude
            Photo_sim[i]['Meas'] = magABzp  ##magnitude with offset
            Photo_sim[i]['Flux'] = fluxABzp ## flux with offset
            Photo_sim[i]['Err']  = numpy.abs(err) ##err on the magnitude
            Photo_sim[i]['FluxErr'] = flux_err###error on the flux
            Photo_sim[i]['Leff'] = Leff ### effective wavelength of the filter 
            Photo_sim[i]['wave_err'] = FWHM / 2. 

        return Photo_sim

    def simulate_error_phot(self, m, sig):
        '''
        Method that simulate the error on the flux
        from the mean and sigma given by the user
        '''
        ##extract mean and sigma
        sigma = sig
        mu = m

        ##random generation of the error
        s = numpy.random.normal(mu, sigma, 1)
        return s[0]


    def Compute_mag_from_template(self, wave, flux, band, sky):
        '''
        This method compute the magnitude from a template (wave, flux)

        Parameter:
        sky     obj,  sky configuration for this simulation
        ----------
        wave    list, of redshifted wavelength
        flux    list, of redshifted flux
        band    str,  name of the band in which we want to normalize the template
        sky     obj,  sky properties of this simulation

        Return:
        -------
        flux_Norm list, of normlized and redshifted flux
        '''

        if isinstance(band, str):  #<--the case if call from normaliation
            usesky = band.strip('()').split(',')[-2].strip()
            skysub = band.strip('()').split(',')[-1].strip()
            bandname = band.strip('()').split(',')[0].strip()
        else: ##<---normal case during simulation
            usesky = band[-2]
            skysub = band[-1]
            bandname = band[0]

        fluxcp = copy.copy(flux)

        ##check if we need to apply sky
        if usesky != 'none':
            ##we apply the sky emission
            ###regrid sky on template wavelength
            #Sky spectrum
            OH = sky.sky[usesky]['OH'] 
            indexs = numpy.where((OH[0] >= wave[0]) & (OH[0] <= wave[-1]))[0]
            OHw = OH[0][indexs]
            OHext = OH[1][indexs] 
            OHtemp = numpy.interp(wave, OH[0], OH[1])

            ##applu everything
            flux_final = (fluxcp + OHtemp) 
            ###remove sky given by sky substraction accuracy
            flux_skysub = flux_final - skysub * OHtemp

        else:
            flux_skysub = fluxcp

        ###convert template to frequence space
        freqTemp, Template_hz = self.convert_wave_to_freq(wave, flux_skysub)

        ###retrieve filter information
        Lambda, Tran, Leff, \
                FWHM = filters.Retrieve_Filter_inf(self.filterfile).retrieve_one_filter(bandname)

        ##interpolate the filter throughput to the wavelength grid
        Trans_wave_model = numpy.interp(wave, Lambda, Tran)
        ##and Normalise it
        ###WARNING!!: [::-1] because for the integration of y=f(x), x must be increasing
        Normalisation = numpy.trapz(Trans_wave_model, freqTemp[::-1])
        TranfreqNormed = Trans_wave_model / Normalisation
        
        ###make the integration
        integration = numpy.trapz(Template_hz*TranfreqNormed, freqTemp[::-1])

        ###and compute magnitude
        MagAB = -2.5*numpy.log10(integration)-48.60

        Fluxmag = self.mag2flux(MagAB, Leff)
        
        #plt().Filter_template(wave, flux, Lambda, Tran, Leff, FWHM, Fluxmag)
        return MagAB, Fluxmag, Leff, FWHM


    def convert_wave_to_freq(self, wave, Templates):
        '''
        Module that convert an array of Template in erg/s/cm2/Ang to
                            an array of Template in erg/s/cm2/Hz

        To make this computation we follow
              lambda*F(lambda) = nu * F(nu)
              so F(nu) = (lambda/nu) * F(lambda)
        and since nu = c / lambda
           --> So we have F(nu) = (lambda^2 / c) * F(lambda)

        Note: It works also for individual templates
        ----
        Parameter
        ---------
        wave        1D array, wavelength of the template
        Templates   ND array, of template flux in erg/s/cm2/Ang

        Return
        ------
        Template_hz NDarray, of template flux in erg/s/cm2/Ang
        freq        1Darray, of freq from the wavelength
        '''

        ## so we retrieve the speed of light and convert it to Ang/s
        c = units.length().m_to_ang(units.Phys_const().speed_of_light_ms())
        ##and finally we convert the array
        Template_hz = Templates * (wave**2/c)
        ## and the wavelength
        freq = c / wave

        return freq, Template_hz


    def mag2flux(self, mag, Leff):
        '''        
        Method that convert magnitude into flux in Ang
        Parameter
        ---------
        mag     float or list of float, of magnitude in AB system to compute
        Leff    float, effective wavelength of the filter

        Return
        ------
        flux_ang    float, corresponding flux in erg/s/cm2/Ang

        '''

        ##we convert the magniude (or array of magnitude). This gives a flux in 
        ## erg/s/cm2/Hz
        flux_hz = 10**((mag+48.6)/(-2.5))

        ## so we retrieve the speed of light and convert it to Ang/s
        c = units.length().m_to_ang(units.Phys_const().speed_of_light_ms())

        ## and then convert it into erg/s/cm2/ang
        flux_Ang = (c / Leff**2) * flux_hz 

        return flux_Ang
